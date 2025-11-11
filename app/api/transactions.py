# app/api/transactions.py

from datetime import datetime
from sqlalchemy import func
from fastapi import APIRouter, Request
from sqlmodel import Session, select
from app.db import engine
from app.models import Transaction
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
