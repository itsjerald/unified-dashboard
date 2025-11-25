from fastapi import APIRouter, Request, HTTPException, Depends
from sqlmodel import Session, select
from app.db import engine, get_session
from app.auth import get_current_user, hash_password
from app.models import User, Family

router = APIRouter()

@router.post("/change-password")
def change_password(request: Request, payload: dict):
    user = get_current_user(request)
    old_pw = payload.get("old_password")
    new_pw = payload.get("new_password")

    if not old_pw or not new_pw:
        raise HTTPException(400, "Missing fields")

    with Session(engine) as session:
        u = session.get(User, user.id)
        if not u:
            raise HTTPException(404, "User not found")
        from app.auth import verify_password
        if not verify_password(old_pw, u.password_hash):
            raise HTTPException(403, "Incorrect password")
        u.password_hash = hash_password(new_pw)
        u.first_login = False
        session.add(u)
        session.commit()
    return {"message": "Password changed successfully"}


