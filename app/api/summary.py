# app/api/summary.py

from fastapi import APIRouter, Request
from datetime import datetime, timedelta
from sqlmodel import Session, select
from sqlalchemy import func
from app.db import engine
from app.auth import get_current_user
from app.models import Transaction, Payment

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
