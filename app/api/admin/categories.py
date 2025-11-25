# app/api/admin/categories.py
from fastapi import APIRouter, Request, HTTPException
from sqlmodel import Session, select
from app.db import engine
from app.models import Category, MerchantRule
from app.api.admin.common import require_admin, require_parent_or_spouse

router = APIRouter()

# -------------------------------
# GET ALL CATEGORIES
# -------------------------------
@router.get("/categories")
def get_categories(request: Request):
    user = require_parent_or_spouse(request)
    with Session(engine) as session:
        rows = session.exec(select(Category).where(Category.family_id == user.family_id)).all()
    return [{"id": c.id, "name": c.name} for c in rows]


# -------------------------------
# CREATE CATEGORY
# -------------------------------
@router.post("/categories")
def create_category(request: Request, payload: dict):
    require_parent_or_spouse(request)
    name = payload.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="name required")

    with Session(engine) as session:
        cat = Category(name=name)
        session.add(cat)
        session.commit()
        session.refresh(cat)
    return {"id": cat.id, "name": cat.name}


# -------------------------------
# DELETE CATEGORY
# -------------------------------
@router.delete("/categories/{cat_id}")
def delete_category(request: Request, cat_id: int):
    require_parent_or_spouse(request)
    with Session(engine) as session:
        cat = session.get(Category, cat_id)
        if not cat:
            raise HTTPException(status_code=404, detail="Category not found")

        # Prevent deletion if rules use this category
        rule = session.exec(select(MerchantRule).where(MerchantRule.category_id == cat_id)).first()
        if rule:
            raise HTTPException(status_code=400, detail="Category used in merchant rules. Delete rules first.")

        session.delete(cat)
        session.commit()

    return {"deleted": cat_id}
