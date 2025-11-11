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
    allow_origins=["http://127.0.0.1:9000", "http://localhost:9000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Create default admin
def ensure_default_admin():
    with Session(engine) as session:
        admin_exists = session.exec(select(User).where(User.role == "admin")).first()
        if not admin_exists:
            pw_hash = argon2.hash("admin123")
            admin = User(
                email="admin@example.com",
                password_hash=pw_hash,
                role="admin",
                first_login=True
            )
            session.add(admin)
            session.commit()
            print("✅ Default admin created: admin@example.com / admin123")
        else:
            print("🔸 Admin already exists")

ensure_default_admin()

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

# ✅ Default route → redirect to login
@app.get("/")
async def root(request: Request):
    token = request.cookies.get("access_token")
    data = verify_token(token) if token else None
    if data:
        return RedirectResponse(url="/dashboard.html")
    return RedirectResponse(url="/login.html")


# ✅ Static files (keep last)
app.mount("/", StaticFiles(directory="static", html=True), name="static")
