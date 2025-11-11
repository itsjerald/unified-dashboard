# app/api/admin/system.py
from fastapi import APIRouter, Request, HTTPException
from sqlmodel import Session, select
from sqlalchemy import func
from app.db import engine
from app.models import Transaction, User
from app.api.admin.common import require_admin

router = APIRouter()

# -------------------------------
# SYSTEM SUMMARY
# -------------------------------
@router.get("/system")
def admin_system(request: Request):
    require_admin(request)
    with Session(engine) as session:
        total_users = session.exec(select(func.count(User.id))).one()
        total_txn = session.exec(select(func.count(Transaction.id))).one()
        total_unpaid = session.exec(select(func.count(Transaction.id)).where(Transaction.paid == False)).one()

    return {
        "total_users": total_users,
        "total_txn": total_txn,
        "total_unpaid": total_unpaid,
    }


# -------------------------------
# TOP MERCHANTS
# -------------------------------
@router.get("/merchants")
def admin_merchants(request: Request):
    require_admin(request)
    with Session(engine) as session:
        q = (
            select(Transaction.merchant, func.sum(Transaction.amount))
            .group_by(Transaction.merchant)
            .order_by(func.sum(Transaction.amount).desc())
            .limit(20)
        )
        rows = session.exec(q).all()
    return [{"merchant": r[0], "total": r[1]} for r in rows]


# -------------------------------
# DAILY TOTALS
# -------------------------------
@router.get("/daily")
def admin_daily(request: Request):
    require_admin(request)
    with Session(engine) as session:
        q = (
            select(
                func.strftime("%Y-%m-%d", Transaction.date).label("day"),
                func.sum(Transaction.amount)
            )
            .group_by("day")
            .order_by("day")
        )
        rows = session.exec(q).all()

    return [{"date": r[0], "total": r[1]} for r in rows]


# -------------------------------
# MONTHLY TOTALS
# -------------------------------
@router.get("/monthly")
def admin_monthly(request: Request):
    require_admin(request)
    with Session(engine) as session:
        q = (
            select(
                func.strftime("%Y-%m", Transaction.date).label("month"),
                func.sum(Transaction.amount)
            )
            .group_by("month")
            .order_by("month")
        )
        rows = session.exec(q).all()

    return [{"month": r[0], "total": r[1]} for r in rows]
