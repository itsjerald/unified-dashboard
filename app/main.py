from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select
from passlib.hash import argon2

from app.db import engine, init_db
from app.auth import verify_token
from app.models import User
from app import auth
from app.api import upload, summary, reports, transactions
from app.api.admin import categories, rules, system

app = FastAPI(title="GPay Weekly Pay")

# ✅ Initialize DB
init_db()

# ✅ Ensure CORS for cookies
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Create default superadmin (recommended)
def ensure_default_superadmin():
    with Session(engine) as session:
        superadmin_exists = session.exec(select(User).where(User.role == "superadmin")).first()
        if not superadmin_exists:
            pw_hash = argon2.hash("superadmin123")
            superadmin = User(
                email="superadmin@example.com",
                password_hash=pw_hash,
                role="superadmin",
                first_login=True
            )
            session.add(superadmin)
            session.commit()
            print("✅ Default superadmin created: superadmin@example.com / superadmin123")
        else:
            print("🔸 Superadmin already exists")

ensure_default_superadmin()

# ✅ Middleware for user context
@app.middleware("http")
async def add_user_to_request(request: Request, call_next):
    token = request.cookies.get("access_token")
    request.state.user_data = None

    if token:
        data = verify_token(token)
        if data:
            user_id = int(data.get("sub"))
            with Session(engine) as session:
                user = session.get(User, user_id)
                if user:
                    request.state.user_data = {
                        "id": user.id,
                        "email": user.email,
                        "role": user.role
                    }

    response = await call_next(request)
    return response

# ✅ Include Routers
app.include_router(auth.router, prefix="/auth")
app.include_router(upload.router, prefix="/api")
app.include_router(summary.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(transactions.router, prefix="/api")
app.include_router(categories.router, prefix="/api/admin")
app.include_router(rules.router, prefix="/api/admin")
app.include_router(system.router, prefix="/api/admin")

# ✅ Default route → redirect to correct dashboard based on role
@app.get("/")
async def root(request: Request):
    token = request.cookies.get("access_token")
    data = verify_token(token) if token else None

    if data:
        user_id = int(data.get("sub"))
        with Session(engine) as session:
            user = session.get(User, user_id)
            if user:
                role = user.role
                if role == "superadmin":
                    return RedirectResponse(url="/dashboard-superadmin.html")
                elif role == "admin":
                    return RedirectResponse(url="/dashboard-admin.html")
                elif role in ("parent", "spouse"):
                    return RedirectResponse(url="/dashboard-parent.html")
                elif role == "child":
                    return RedirectResponse(url="/dashboard-child.html")
                else:
                    # fallback in case new/unknown role
                    return RedirectResponse(url="/dashboard.html")
    return RedirectResponse(url="/login.html")

# ✅ Static files (keep last)
app.mount("/", StaticFiles(directory="static", html=True), name="static")
