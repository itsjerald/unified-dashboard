from datetime import timedelta, datetime

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request, Query
from pydantic import EmailStr
from sqlmodel import select, Session  # CORRECT: use sqlmodel.Session, not requests.Session

from app.auth import get_current_user, generate_token, send_verification_email
from app.db import get_session
from app.utils.email import get_family_smtp
from app.models import User, Transaction, TxnShareRequest, Family, Category

from app.utils.permissions import (
    require_superadmin,
    require_admin_or_superadmin,
    require_parent,
    require_parent_or_spouse,
    require_verified
)

DEFAULT_CATEGORIES = ["Groceries", "Utilities", "Transport", "School", "Medical", "Shopping"]

router = APIRouter()

@router.get("/transactions/family")
def get_family_transactions(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    require_parent_or_spouse(current_user)
    txns = session.exec(
        select(Transaction).where(
            Transaction.family_id == current_user.family_id,
            Transaction.shared == True
        )
    ).all()
    return txns
@router.post("/transactions/share")
def share_transactions(
    req: TxnShareRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    txns = session.exec(
        select(Transaction).where(
            Transaction.user_id == current_user.id,
            Transaction.id.in_(req.txn_ids),
            Transaction.shared == False,
            Transaction.marked_for_deletion == False
        )
    ).all()
    for txn in txns:
        txn.shared = True
        session.add(txn)
    session.commit()
    return {"shared": [txn.id for txn in txns]}

@router.post('/family/invite')
def invite_family(
    email: EmailStr,
    role: str,
    request: Request,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session)
):
    inviter = get_current_user(request)
    require_parent_or_spouse(inviter)
    require_verified(inviter)
    # Only allow certain roles to be invited
    allowed_roles = ['spouse', 'child', 'sibling']
    if role not in allowed_roles:
        raise HTTPException(status_code=400, detail="Invalid role.")

    # Prevent duplicate email
    existing = session.exec(select(User).where(User.email == email)).first()
    if existing:
        # Allow inviting a spouse without family
        if existing.role == "spouse" and not existing.family_id:
            existing.family_id = inviter.family_id
            existing.parent_id = None
            existing.verification_token = generate_token()
            existing.is_verified = False
            session.add(existing)
            session.commit()
            background_tasks.add_task(
                send_verification_email, email, existing.verification_token, get_family_smtp(inviter.family_id)
            )
            return {
                "message": "Existing spouse invited. Must verify and join the family.",
                "user_id": existing.id
            }
        raise HTTPException(status_code=400, detail="Email already exists")

    # Permission logic per role
    if role == "spouse":
        if inviter.role != "parent":
            raise HTTPException(status_code=403, detail="Only parent can invite spouse.")
        parent_id = None
    elif role == "child":
        if inviter.role not in ("parent", "spouse"):
            raise HTTPException(status_code=403, detail="Only parent or spouse can invite child.")
        parent_id = inviter.id
    elif role == "sibling":
        if inviter.role != "child" or not inviter.parent_id:
            raise HTTPException(status_code=403, detail="Only child can invite sibling.")
        parent_id = inviter.parent_id

    token = generate_token()
    new_user = User(
        email=email,
        role=role,
        family_id=inviter.family_id,
        parent_id=parent_id,
        is_verified=False,
        verification_token=token,
        invited_by_id=inviter.id,
        created_at=datetime.utcnow()
    )
    session.add(new_user)
    session.commit()
    session.refresh(new_user)

    background_tasks.add_task(
        send_verification_email, email, token, get_family_smtp(inviter.family_id)
    )

    return {
        "message": f"{role.capitalize()} invited. Must verify within 7 days.",
        "user_id": new_user.id,
        "expires": (datetime.utcnow() + timedelta(days=7)).isoformat()
    }

@router.post("/family/create")
def create_family(
    request: Request,
    payload: dict,
    session: Session = Depends(get_session)
):
    user = get_current_user(request)
    require_parent(user)
    require_verified(user)

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

    # Assign default categories
    for cat_name in DEFAULT_CATEGORIES:
        session.add(Category(name=cat_name, family_id=family.id))
    session.commit()

    user.family_id = family.id
    user.first_login = False
    session.add(user)
    session.commit()
    return {"message": f"Family '{name}' created", "family_id": family.id}

@router.get("/family/join")
def join_family_with_token(
    token: str = Query(..., description="Verification/invite token"),
    session: Session = Depends(get_session)
):
    user = session.exec(select(User).where(User.verification_token == token)).first()
    if not user:
        raise HTTPException(404, "Invalid or expired invite link.")

    # Check role (spouse, child, sibling - you can expand allowed roles)
    allowed_roles = ["spouse", "child", "sibling"]
    if user.role not in allowed_roles:
        raise HTTPException(400, "Invalid invitee role.")

    # Already in a family check (optionally you may want to allow moving)
    if user.family_id is None:
        raise HTTPException(400, "Invite not linked to a family. Please contact your inviter.")
    if user.is_verified:
        return {"message": "Already part of the family (verified)."}

    user.is_verified = True
    user.verification_token = None
    session.add(user)
    session.commit()
    return {
        "message": f"Welcome, you have joined family #{user.family_id} successfully!",
        "family_id": user.family_id,
        "role": user.role,
        "email": user.email
    }
