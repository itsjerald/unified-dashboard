# app/api/transactions.py

from datetime import datetime
from sqlalchemy import func
from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.sql.functions import current_user
from sqlmodel import Session, select
from app.db import engine, get_session
from app.models import Transaction, User, Payment
from app.auth import get_current_user

router = APIRouter()

@router.get("/transactions")
def list_transactions(request: Request, start: str = None, end: str = None):
    user = get_current_user(request)

    with Session(engine) as session:
        q = select(Transaction).where(Transaction.user_id == user.id)

        if start:
            q = q.where(func.date(Transaction.date) >= datetime.fromisoformat(start).date())
        if end:
            q = q.where(func.date(Transaction.date) <= datetime.fromisoformat(end).date())

        rows = session.exec(q.order_by(Transaction.date.desc())).all()

    return [
        {
            "id": t.id,
            "date": t.date.isoformat(),
            "amount": t.amount,
            "merchant": t.merchant,
            "category": t.category,
            "paid": t.paid,
        }
        for t in rows
    ]


@router.post("/transactions/archive")
def archive_transactions(request: Request, payload: dict):
    user = get_current_user(request)
    ids = payload.get("ids", [])

    with Session(engine) as session:
        updated = 0
        for tid in ids:
            t = session.get(Transaction, tid)
            if t and t.user_id == user.id:
                t.paid = True
                session.add(t)
                updated += 1

        session.commit()

    return {"archived": updated}

@router.get("/debug/txns")
def debug_txns(request: Request):
    """Returns last 20 transactions for debugging."""
    user = get_current_user(request)
    with Session(engine) as session:
        rows = session.exec(
            select(Transaction)
            .where(Transaction.user_id == user.id)
            .order_by(Transaction.date.desc())
        ).all()

    return [
        {
            "id": t.id,
            "amount": t.amount,
            "merchant": t.merchant,
            "paid": t.paid,
            "date": t.date.isoformat(),
        }
        for t in rows[:20]
    ]

@router.get("/transactions/")
def get_user_transactions(current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    return session.exec(select(Transaction).where(Transaction.user_id == current_user.id)).all()

@router.post("/users/{user_id}/map_parent/{parent_id}")
def map_parent(user_id: int, parent_id: int, session: Session = Depends(get_session)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can map users to parents")
    user = session.get(User, user_id)
    parent = session.get(User, parent_id)
    if parent.role != "admin":
        raise HTTPException(status_code=400, detail="Parent must be an admin")
    user.parent_id = parent_id
    session.add(user)
    session.commit()
    return {"message": f"User {user.email} mapped to parent {parent.email}"}

@router.delete("/transactions/{txn_id}")
def delete_transaction(txn_id: int, current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    txn = session.get(Transaction, txn_id)
    if not txn or txn.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if txn.shared:
        raise HTTPException(status_code=400, detail="Cannot delete shared transactions")
    session.delete(txn)
    session.commit()
    return {"message": "Deleted successfully"}

@router.post("/transactions/share")
def share_transactions(payload: dict, current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    ids = payload.get("ids", [])
    if not ids:
        raise HTTPException(status_code=400, detail="No transactions selected")

    txns = session.exec(
        select(Transaction).where(
            Transaction.user_id == current_user.id,
            Transaction.id.in_(ids),
            Transaction.shared == False
        )
    ).all()
    for txn in txns:
        txn.shared = True
        session.add(txn)
    session.commit()
    return {"message": f"Shared {len(txns)} transactions to parent"}



@router.get("/admin/shared")
def get_shared_transactions(current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")

    shared = session.exec(
        select(Transaction, User)
        .join(User)
        .where(User.parent_id == current_user.id, Transaction.shared == True)
        .where(User.parent_id == current_user.id, User.family_id == current_user.family_id)
    ).all()

    result = []
    for txn, user in shared:
        result.append({
            "id": txn.id,
            "user_email": user.email,
            "date": txn.date.isoformat(),
            "merchant": txn.merchant,
            "amount": txn.amount,
            "paid": txn.paid
        })
    return result

@router.post("/admin/markPaid")
def admin_mark_paid(payload: dict, current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")

    txn_ids = payload.get("txnIds", [])
    updated = 0
    for tid in txn_ids:
        txn = session.get(Transaction, tid)
        if not txn:
            continue
        # verify txn belongs to a child user
        child = session.get(User, txn.user_id)
        if child.parent_id != current_user.id:
            continue
        txn.paid = True
        session.add(txn)
        updated += 1

    session.commit()
    return {"marked": updated}

@router.post("/api/admin/pay")
def pay_user(payload: dict, current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403)
    payee_id = payload["payee_id"]
    amount = payload["amount"]
    txn_refs = payload.get("txn_refs", [])
    payment = Payment(payer_id=current_user.id, payee_id=payee_id, amount=amount, txn_refs=txn_refs)
    session.add(payment)
    session.commit()
    return {"message": "Payment recorded"}

