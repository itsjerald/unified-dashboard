from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from pydantic import BaseModel, EmailStr
from app.db import engine
from app.models import User
from sqlmodel import Session, select
from passlib.hash import argon2
from datetime import datetime, timedelta
from jose import JWTError, jwt
import os
import pyotp

router = APIRouter()

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
            role=payload.role if payload.role in ["admin", "user"] else "user",
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
    First user creation (admin) handled separately in main.py.
    """
    with Session(engine) as session:
        existing = session.exec(select(User).where(User.email == payload.email)).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already exists")

        pw_hash = hash_password(payload.password)

        new_user = User(
            email=payload.email,
            password_hash=pw_hash,
            role="user",          # Always user for public signup
            first_login=True
        )

        session.add(new_user)
        session.commit()
        session.refresh(new_user)

        return {"message": "Account created successfully. Please login.", "redirect": "/login.html"}
