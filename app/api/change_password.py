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

@router.post("/family/create")
def create_family(request: Request, payload: dict, session: Session = Depends(get_session)):
    user = get_current_user(request)
    if user.role != "admin":
        raise HTTPException(403, "Only admins can create families")
    if user.family_id:
        raise HTTPException(400, "You already belong to a family")

    name = payload.get("name")
    if not name:
        raise HTTPException(400, "Family name required")

    existing = session.exec(select(Family).where(Family.name == name)).first()
    if existing:
        raise HTTPException(400, "Family name already exists")

    family = Family(name=name)
    session.add(family)
    session.commit()
    session.refresh(family)

    user.family_id = family.id
    user.first_login = False
    session.add(user)
    session.commit()
    return {"message": f"Family '{name}' created", "family_id": family.id}

@router.post("/family/join")
def join_family(request: Request, payload: dict, session: Session = Depends(get_session)):
    user = get_current_user(request)
    if user.family_id:
        raise HTTPException(400, "Already in a family")

    name = payload.get("name")
    family = session.exec(select(Family).where(Family.name == name)).first()
    if not family:
        raise HTTPException(404, "Family not found")

    user.family_id = family.id
    user.first_login = False
    session.add(user)
    session.commit()
    return {"message": f"Joined family '{name}'", "family_id": family.id}

