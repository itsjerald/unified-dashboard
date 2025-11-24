from fastapi import APIRouter, Depends, HTTPException
from requests import Session
from sqlmodel import select

from app.auth import get_current_user
from app.db import get_session
from app.models import User, Transaction, TxnShareRequest, DeletionRequest, Family

router = APIRouter()

@router.get("/transactions/family")
def get_family_transactions(current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    # assuming current_user.family_id is set
    txns = session.exec(
        select(Transaction).where(
            Transaction.family_id == current_user.family_id,
            Transaction.shared == True
        )
    ).all()
    return txns

@router.post("/transactions/share")
def share_transactions(req: TxnShareRequest, current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
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

@router.post("/admin/request_delete")
def request_delete(entity_type: str, entity_id: int, current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    if current_user.role != "superadmin":
        raise HTTPException(status_code=403)
    # Check not already pending
    pending = session.exec(
        select(DeletionRequest).where(
            DeletionRequest.entity_type == entity_type,
            DeletionRequest.entity_id == entity_id,
            DeletionRequest.executed == False
        )
    ).first()
    if pending:
        raise HTTPException(status_code=400, detail="Deletion already pending")
    req = DeletionRequest(entity_type=entity_type, entity_id=entity_id, requested_by_id=current_user.id)
    session.add(req)
    session.commit()
    return {"message": "Deletion request submitted"}

@router.post("/admin/approve_delete/{request_id}")
def approve_delete(request_id: int, current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    req = session.get(DeletionRequest, request_id)
    if not req or req.executed:
        raise HTTPException(status_code=404)
    if current_user.role != "superadmin" or current_user.id == req.requested_by_id or current_user.id in req.approval_ids:
        raise HTTPException(status_code=403)
    req.approval_ids.append(current_user.id)
    session.add(req)
    # If 2 approvals (not including requester), execute delete
    if len(req.approval_ids) >= 2:
        # Delete entity based on type (user/family)
        if req.entity_type == "user":
            user = session.get(User, req.entity_id)
            if user: session.delete(user)
        elif req.entity_type == "family":
            family = session.get(Family, req.entity_id)
            if family: session.delete(family)
        req.executed = True
    session.commit()
    return {"message": "Approval registered, deletion occurred" if req.executed else "Approval registered"}
