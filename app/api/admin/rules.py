# api/admin/rules.py

from fastapi import APIRouter, Request, HTTPException
from sqlmodel import Session, select

from app.db import engine
from app.models import MerchantRule, Category
from app.api.admin.common import require_admin



router = APIRouter()


# -----------------------
# LIST RULES
# -----------------------
@router.get("/merchant-rules")
def get_rules(request: Request):
    require_admin(request)

    with Session(engine) as session:
        rows = session.exec(
            select(MerchantRule, Category).join(Category)
        ).all()

    return [
        {
            "id": rule.id,
            "pattern": rule.pattern,
            "category": category.name,
            "category_id": category.id,
        }
        for rule, category in rows
    ]


# -----------------------
# CREATE RULE
# -----------------------
@router.post("/merchant-rules")
def create_rule(request: Request, payload: dict):
    require_admin(request)

    pattern = payload.get("pattern")
    category_id = payload.get("category_id")

    if not pattern or not category_id:
        raise HTTPException(400, "pattern and category_id required")

    with Session(engine) as session:
        # validate category exists
        cat = session.get(Category, category_id)
        if not cat:
            raise HTTPException(404, "Category not found")

        r = MerchantRule(
            pattern=pattern.upper(),
            category_id=category_id
        )
        session.add(r)
        session.commit()
        session.refresh(r)

    return {"id": r.id, "pattern": r.pattern, "category_id": r.category_id}


# -----------------------
# DELETE RULE
# -----------------------
@router.delete("/merchant-rules/{rule_id}")
def delete_rule(request: Request, rule_id: int):
    require_admin(request)

    with Session(engine) as session:
        r = session.get(MerchantRule, rule_id)
        if not r:
            raise HTTPException(404, "Rule not found")

        session.delete(r)
        session.commit()

    return {"deleted": rule_id}
