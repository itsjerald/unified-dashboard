from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.models import Family, User
from app.auth import get_current_user
from app.db import get_session

router = APIRouter()

# ---------- Role Check Utility Functions ----------
def require_superadmin(user: User):
    if user.role != "superadmin":
        raise HTTPException(status_code=403, detail="Superadmin privilege required")
    return user

def require_admin_or_superadmin(user: User):
    if user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Admin privilege required")
    return user

# ---------- List all families (admin/superadmin only) ----------
@router.get("/families")
def list_families(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    require_admin_or_superadmin(current_user)
    families = session.exec(select(Family)).all()
    return [{"id": f.id, "name": f.name, "created_at": f.created_at} for f in families]

# ---------- Create a family (admin/superadmin only) ----------
@router.post("/families")
def create_family(
    name: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    require_admin_or_superadmin(current_user)
    if session.exec(select(Family).where(Family.name == name)).first():
        raise HTTPException(status_code=400, detail="Family name already exists")
    family = Family(name=name)
    session.add(family)
    session.commit()
    return {"id": family.id, "name": family.name}

# ---------- Delete a family (superadmin only) ----------
@router.delete("/families/{family_id}")
def delete_family(
    family_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    require_superadmin(current_user)
    family = session.get(Family, family_id)
    if not family:
        raise HTTPException(status_code=404, detail="Family not found")
    session.delete(family)
    session.commit()
    return {"deleted": family_id}

# ---------- List all parents/children in a family (admin/superadmin only) ----------
@router.get("/families/{family_id}/members")
def list_family_members(
    family_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    require_admin_or_superadmin(current_user)
    users = session.exec(select(User).where(User.family_id == family_id)).all()
    return [
        {"id": u.id, "email": u.email, "role": u.role, "is_verified": u.is_verified}
        for u in users
    ]

# ---------- Parent-only self actions go to family.py (not included here) ----------
