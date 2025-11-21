from fastapi import APIRouter, Depends
from requests import Session
from sqlmodel import select

from app.auth import get_current_user
from app.db import get_session
from app.models import User, Transaction, TxnShareRequest

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