# app/api/summary.py

from fastapi import APIRouter, Request, Depends, HTTPException
from datetime import datetime, timedelta
from sqlmodel import Session, select
from sqlalchemy import func
from app.db import engine, get_session
from app.auth import get_current_user
from app.models import Transaction, Payment, User

router = APIRouter()

@router.get("/summary")
def summary(request: Request, days: int = 7):
    user = get_current_user(request)

    end = datetime.utcnow().date()
    start = end - timedelta(days=days)

    with Session(engine) as session:
        q = (
            select(Transaction)
            .where(
                Transaction.user_id == user.id,
                Transaction.paid == False,
                func.date(Transaction.date) >= start,
                func.date(Transaction.date) <= end
            )
        )
        rows = session.exec(q).all()

    total = sum(t.amount for t in rows)
    items = [
        {"id": t.id, "date": t.date.isoformat(), "amount": t.amount, "merchant": t.merchant}
        for t in rows
    ]

    return {"unpaid": items, "total": total, "upi": "friend@upi", "name": "Friend"}


@router.post("/markPaid")
def mark_paid(request: Request, payload: dict):
    user = get_current_user(request)
    txn_ids = payload.get("txnIds", [])

    with Session(engine) as session:
        updated = 0
        for tid in txn_ids:
            t = session.get(Transaction, tid)
            if t and not t.paid:
                t.paid = True
                session.add(t)
                updated += 1
        session.commit()

    return {"marked": updated}

@router.get("/admin/summary")
def get_summary(
    start_date: datetime,
    end_date: datetime,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    total = session.exec(
        select(func.sum(Transaction.amount))
        .join(User)
        .where(
            User.parent_id == current_user.id,
            Transaction.shared == True,
            Transaction.date.between(start_date, end_date)
        )
        .where(User.parent_id == current_user.id, User.family_id == current_user.family_id)
    ).one_or_none()
    return {"total": float(total[0]) if total and total[0] else 0}
