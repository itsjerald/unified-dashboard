from fastapi import APIRouter, HTTPException, Response, Request, Depends
from pydantic import BaseModel, EmailStr
from app.db import engine, get_session
from app.utils.email import get_family_smtp
from app.models import User, Family, VerificationResendLog
from sqlmodel import Session, select
from passlib.hash import argon2
from datetime import datetime, timedelta
from jose import JWTError, jwt
import os
import pyotp
import secrets
import smtplib, ssl
from email.message import EmailMessage

from app.settings import DEFAULT_SMTP

router = APIRouter()
VALID_ROLES = ["superadmin", "admin", "parent", "child", "spouse", "user"]

SECRET_KEY = os.environ.get('SECRET_KEY', 'change-me-in-prod')
ALGORITHM = 'HS256'
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get('ACCESS_TOKEN_EXPIRE_MINUTES', '60'))

class RegisterIn(BaseModel):
    email: EmailStr
    password: str
    role: str = "user"


class LoginIn(BaseModel):
    email: EmailStr
    password: str

class ChangePasswordIn(BaseModel):
    old_password: str
    new_password: str

def generate_token(length: int = 32) -> str:
    """
    Generate a secure random token for email verification.
    """
    return secrets.token_urlsafe(length)

@router.post('/change-password')
def change_password(request: Request, payload: ChangePasswordIn):
    user = get_current_user(request)
    with Session(engine) as session:
        u = session.get(User, user.id)
        if not u:
            raise HTTPException(status_code=404, detail="User not found")
        if not verify_password(payload.old_password, u.password_hash):
            raise HTTPException(status_code=403, detail="Incorrect old password")
        u.password_hash = hash_password(payload.new_password)
        u.first_login = False
        session.add(u)
        session.commit()
    response = Response()
    response.delete_cookie("force_change_pw")
    return {"message": "Password changed successfully"}


def require_admin(request: Request):
    user = get_current_user(request)
    if user.role != 'admin':
        raise HTTPException(status_code=403, detail='Admin access required')
    return user

def hash_password(password: str) -> str:
    return argon2.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    return argon2.verify(password, hashed)

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({'exp': expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

@router.post('/register')
def register(request: Request, payload: RegisterIn):
    admin = require_admin(request)  # ✅ Only admin can register users

    with Session(engine) as session:
        existing = session.exec(select(User).where(User.email == payload.email)).first()
        if existing:
            raise HTTPException(status_code=400, detail='Email already exists')

        pw_hash = hash_password(payload.password)
        new_user = User(
            email=payload.email,
            password_hash=pw_hash,
            role=payload.role if payload.role in ["admin", "superadmin", "parent", "child", "spouse",
                                                  "user"] else "user",
            first_login=True
        )

        session.add(new_user)
        session.commit()
        session.refresh(new_user)

        return {"id": new_user.id, "email": new_user.email, "role": new_user.role}


@router.post('/login')
def login(payload: LoginIn, response: Response):
    with Session(engine) as session:
        q = select(User).where(User.email == payload.email)
        user = session.exec(q).first()
        if not user or not argon2.verify(payload.password, user.password_hash):
            raise HTTPException(status_code=401, detail='Invalid credentials')

        token = create_access_token({'sub': str(user.id), 'email': user.email})
        response.set_cookie('access_token', token, httponly=True, secure=False, samesite='lax')

        # ✅ First-login flag for front-end redirect
        if user.first_login:
            response.set_cookie('force_change_pw', '1', httponly=False)
        else:
            response.delete_cookie('force_change_pw')

        return {"message": "logged_in", "email": user.email, "role": user.role, "first_login": user.first_login}

@router.post('/logout')
def logout(response: Response):
    response.delete_cookie('access_token')
    return {'message': 'logged_out'}

def get_current_user(request: Request):
    token = request.cookies.get('access_token')
    if not token:
        raise HTTPException(status_code=401, detail='Not authenticated')
    data = verify_token(token)
    if not data:
        raise HTTPException(status_code=401, detail='Invalid token')
    user_id = int(data.get('sub'))
    with Session(engine) as session:
        user = session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=401, detail='User not found')
        return user

@router.post('/enable-totp')
def enable_totp(request: Request):
    user = get_current_user(request)
    secret = pyotp.random_base32()
    # save secret temporarily; in production use proper onboarding flow
    with Session(engine) as session:
        user_db = session.get(User, user.id)
        user_db.totp_secret = secret
        session.add(user_db)
        session.commit()
    uri = pyotp.totp.TOTP(secret).provisioning_uri(name=user.email, issuer_name='GPayWeeklyPay')
    return {'secret': secret, 'uri': uri}

@router.post('/verify-totp')
def verify_totp(code: str, request: Request):
    user = get_current_user(request)
    if not user.totp_secret:
        raise HTTPException(status_code=400, detail='No totp enabled')
    totp = pyotp.TOTP(user.totp_secret)
    if not totp.verify(code):
        raise HTTPException(status_code=400, detail='Invalid code')
    return {'verified': True}

@router.get("/me")
def me(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return {"authenticated": False}

    data = verify_token(token)
    if not data:
        return {"authenticated": False}

    user_id = int(data.get("sub"))

    with Session(engine) as session:
        user = session.get(User, user_id)
        if not user:
            return {"authenticated": False}

        return {
            "authenticated": True,
            "user_id": user.id,
            "email": user.email,
            "role": user.role if hasattr(user, "role") else "user"
        }

@router.get("/admin/users")
def list_users(request: Request):
    admin = require_admin(request)
    with Session(engine) as session:
        users = session.exec(select(User)).all()
        return [
            {"email": u.email, "role": u.role, "first_login": u.first_login}
            for u in users
        ]

@router.post('/signup')
def signup(payload: RegisterIn):
    """
    Public signup endpoint.
    Normal users can self-register.
    Sends verification email. User must verify within 7 days.
    """
    with Session(engine) as session:
        existing = session.exec(select(User).where(User.email == payload.email)).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already exists")

        pw_hash = hash_password(payload.password)
        token = generate_token()
        expires_at = datetime.utcnow() + timedelta(days=7)

        smtp_cfg = DEFAULT_SMTP

        new_user = User(
            email=payload.email,
            password_hash=pw_hash,
            role=payload.role if payload.role in ["parent", "child", "spouse", "user"] else "user",
            first_login=True,
            is_verified=False,
            verification_token=token,
            created_at=datetime.utcnow(),
            verification_expires_at=expires_at
        )

        # If family_id set, use family's smtp
        if new_user.family_id:
            smtp_cfg = get_family_smtp(new_user.family_id)

        # Only create/save user after email is sent
        send_verification_email(payload.email, token, smtp_cfg)
        session.add(new_user)
        session.commit()
        session.refresh(new_user)

        return {"message": "Account created. Check your email to verify!", "redirect": "/login.html"}


def send_verification_email(email: str, token: str, smtp_cfg: dict):
    try:
        msg = EmailMessage()
        msg["Subject"] = "Verify your FamilyApp account"
        msg["From"] = smtp_cfg['EMAIL_USER']
        msg["To"] = email
        APP_HOST_URL = os.environ.get('APP_HOST_URL', 'http://localhost:8000')
        verify_url = f"{APP_HOST_URL}/auth/verify?token={token}"
        msg.set_content(f"Welcome! Please verify your account: {verify_url}")

        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(smtp_cfg['EMAIL_HOST'], smtp_cfg['EMAIL_PORT'], context=context) as server:
            server.login(smtp_cfg['EMAIL_USER'], smtp_cfg['EMAIL_PASS'])
            server.send_message(msg)
    except Exception as e:
        print(f"Email sending failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to send verification email. Please try again.")


@router.post('/admin/invite_superadmin')
def invite_superadmin(email: EmailStr, request: Request):
    # Only default admin or verified superadmins allowed
    inviter = get_current_user(request)
    if inviter.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403)
    token = generate_token()
    expires_at = datetime.utcnow() + timedelta(days=7)
    user = User(
        email=email,
        role="superadmin",
        first_login=True,
        is_verified=False,
        verification_token=token,
        created_at=datetime.utcnow(),
        verification_expires_at=expires_at
    )

    with Session(engine) as session:
        session.add(user)
        session.commit()
    send_verification_email(email, token, smtp_config=DEFAULT_SMTP)
    return {"message": "Superadmin invited. Must verify within 7 days."}

def cleanup_unverified_accounts():
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    with Session(engine) as session:
        # Find unverified users
        unverified = session.exec(select(User).where(User.is_verified == False, User.created_at < seven_days_ago)).all()
        for user in unverified:
            if user.role == "parent" and user.family_id:
                # Delete entire family and cascade to spouses, children, transactions
                family = session.get(Family, user.family_id)
                if family:
                    session.delete(family)
            else:
                # Delete user; cascade set on relationships deletes transactions, children, etc.
                session.delete(user)
        session.commit()

MAX_RESENDS_PER_DAY = 7
@router.post('/auth/resend-verification')
def resend_verification(email: EmailStr):
    now = datetime.utcnow()
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)
    with Session(engine) as session:
        count_today = session.exec(
            select(VerificationResendLog)
            .where(
                VerificationResendLog.email == email,
                VerificationResendLog.sent_at >= start_of_day,
                VerificationResendLog.sent_at < end_of_day
            )
        ).count()
        if count_today >= MAX_RESENDS_PER_DAY:
            raise HTTPException(status_code=429, detail="Too many resend attempts for today. Try tomorrow.")

        user = session.exec(select(User).where(User.email == email)).first()
        if not user or user.is_verified:
            raise HTTPException(status_code=400, detail="No unverified account for this email.")
        # always issue a fresh expiry for a new token
        token = generate_token()
        expires_at = now + timedelta(days=7)
        send_verification_email(email, token, DEFAULT_SMTP)  # <-- fail early if can't
        user.verification_token = token
        user.verification_expires_at = expires_at
        session.add(user)
        # Log this send
        session.add(VerificationResendLog(email=email, sent_at=now))
        session.commit()
    return {"message": "Verification email resent."}

def get_valid_role(requested_role: str, default: str = "user"):
    return requested_role if requested_role in VALID_ROLES else default

@router.post('/admin/invite_user')
def invite_user(
    email: EmailStr,
    role: str,
    request: Request
):
    inviter = get_current_user(request)
    # Only admin or superadmin can invite any role
    if inviter.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    if role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role: {role}")
    token = generate_token()
    expires_at = datetime.utcnow() + timedelta(days=7)

    with Session(engine) as session:
        # Prevent duplicate emails
        existing = session.exec(select(User).where(User.email == email)).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already exists.")

        user = User(
            email=email,
            role=role,
            first_login=True,
            is_verified=False,
            verification_token=token,
            created_at=datetime.utcnow(),
            verification_expires_at=expires_at
        )
        session.add(user)
        session.commit()

    # Send verification (adapt as needed)
    send_verification_email(email, token, smtp_cfg=DEFAULT_SMTP)
    return {"message": f"{role.capitalize()} invited. Must verify within 7 days."}

from fastapi.responses import HTMLResponse

@router.get("/verify", response_class=HTMLResponse)
def verify_email(token: str, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.verification_token == token)).first()
    if not user:
        # Show error or redirect to login as fallback
        return HTMLResponse(
            content="<script>window.location='/login.html';</script>",
            status_code=404
        )
    user.is_verified = True
    user.verification_token = None
    session.add(user)
    session.commit()
    # After verification, redirect to login (not dashboard!) after 2 seconds
    return HTMLResponse(
        content=f"""
            <html>
            <head>
                <meta http-equiv="refresh" content="2; url=/login.html" />
                <title>Email Verified</title>
                <style>
                  body {{ background: #f3f4f6; font-family: sans-serif; }}
                  .card {{
                    max-width: 410px; margin: 120px auto; padding: 2rem 1.5rem;
                    background: #fff; border-radius: 8px; text-align: center;
                    box-shadow:0 3px 12px 0 rgba(37, 99, 235, 0.08);
                  }}
                  .btn {{
                    display:inline-block; margin-top:1.5rem; padding:12px 30px;
                    background:#2563eb;color:#fff;text-decoration:none;border-radius:5px;font-weight:bold;
                  }}
                </style>
            </head>
            <body>
              <div class="card">
                <h2 style="color:#22c55e;">✅ Email Verified!</h2>
                <p>Hi <b>{user.email}</b>, <br>your email is now verified.</p>
                <p>Redirecting to login page...</p>
                <a href='/login.html' class="btn">Go to Login</a>
              </div>
              <script>
                setTimeout(() => window.location='/login.html', 2000);
              </script>
            </body>
            </html>
        """,
    )
