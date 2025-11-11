# app/api/reports.py

from fastapi import APIRouter, Request
from sqlmodel import Session, select
from sqlalchemy import func
from app.db import engine
from app.auth import get_current_user
from app.models import Transaction, MerchantRule, Category

router = APIRouter()


# -------------------------------
# DAILY REPORT
# -------------------------------
@router.get("/report/daily")
def daily_report(request: Request):
    """User's total spending per day"""
    user = get_current_user(request)

    with Session(engine) as session:
        q = (
            select(
                func.strftime("%Y-%m-%d", Transaction.date).label("day"),
                func.sum(Transaction.amount)
            )
            .where(Transaction.user_id == user.id)
            .group_by("day")
            .order_by("day")
        )
        rows = session.exec(q).all()

    return [{"date": r[0], "total": r[1]} for r in rows]


# -------------------------------
# MONTHLY REPORT
# -------------------------------
@router.get("/report/monthly")
def monthly_report(request: Request):
    """User's total spending per month"""
    user = get_current_user(request)

    with Session(engine) as session:
        q = (
            select(
                func.strftime("%Y-%m", Transaction.date).label("month"),
                func.sum(Transaction.amount)
            )
            .where(Transaction.user_id == user.id)
            .group_by("month")
            .order_by("month")
        )
        rows = session.exec(q).all()

    return [{"month": r[0], "total": r[1]} for r in rows]


# -------------------------------
# CATEGORY REPORT
# -------------------------------
@router.get("/report/category")
def category_report(request: Request):
    """Category totals based on merchant rules"""
    user = get_current_user(request)

    with Session(engine) as session:
        txns = session.exec(
            select(Transaction).where(Transaction.user_id == user.id)
        ).all()

        rules = session.exec(select(MerchantRule, Category).join(Category)).all()

    totals = {}

    for t in txns:
        merchant = (t.merchant or "").upper()
        matched = False

        for rule, cat in rules:
            if rule.pattern in merchant:
                totals[cat.name] = totals.get(cat.name, 0) + t.amount
                matched = True
                break

        if not matched:
            totals["Others"] = totals.get("Others", 0) + t.amount

    return [{"category": k, "total": v} for k, v in totals.items()]


# -------------------------------
# VENDOR REPORT
# -------------------------------
@router.get("/report/vendors")
def vendor_report(request: Request):
    """Total per vendor/merchant"""
    user = get_current_user(request)

    with Session(engine) as session:
        q = (
            select(Transaction.merchant, func.sum(Transaction.amount))
            .where(Transaction.user_id == user.id)
            .group_by(Transaction.merchant)
        )
        rows = session.exec(q).all()

    return [{"merchant": r[0], "total": r[1]} for r in rows]
