from sqlmodel import Session, select
from app.db import engine
from app.models import Category, MerchantRule

# ✅ Default categories
CATEGORIES = [
    "Groceries",
    "Medical",
    "Electronics",
    "Finance",
    "Transport",
    "Food",
    "Shopping",
    "Others"
]

# ✅ Default merchant patterns → categories
RULES = {
    "VEGETABLE": "Groceries",
    "VEG": "Groceries",
    "FRUITS": "Groceries",
    "AR ": "Groceries",
    "AMUDHAM": "Groceries",
    "RATIONS": "Groceries",

    "MEDPLUS": "Medical",
    "PHARMACY": "Medical",

    "MOBILE": "Electronics",
    "MOBILES": "Electronics",
    "SATHYA": "Electronics",

    "ZERODHA": "Finance",
    "GROWW": "Finance",
    "PHONEPE": "Finance",

    "AUTO": "Transport",
    "CAB": "Transport",
    "OLA": "Transport",
    "UBER": "Transport",

    "FOOD": "Food",
    "HOTEL": "Food",
    "RESTAURANT": "Food",

    "STARKINDUSTRIES": "Shopping",
    "AMAZON": "Shopping",
    "FLIPKART": "Shopping"
}


def run():
    with Session(engine) as session:
        # ✅ Create categories if missing
        existing = {c.name for c in session.exec(select(Category)).all()}

        for cat in CATEGORIES:
            if cat not in existing:
                new_cat = Category(name=cat)
                session.add(new_cat)
                session.commit()
                print(f"Added category: {cat}")

        # ✅ Load categories again to map names → ids
        categories = {c.name: c.id for c in session.exec(select(Category)).all()}

        # ✅ Create rules
        existing_patterns = {r.pattern for r in session.exec(select(MerchantRule)).all()}

        for pattern, cat_name in RULES.items():
            if pattern.upper() not in existing_patterns:
                rule = MerchantRule(
                    pattern=pattern.upper(),
                    category_id=categories[cat_name]
                )
                session.add(rule)
                session.commit()
                print(f"Added rule: {pattern} → {cat_name}")

        print("\n✅ Default rules added successfully!")


if __name__ == "__main__":
    run()
