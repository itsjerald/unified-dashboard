# app/utils/email.py

from sqlmodel import Session
from app.db import engine
from app.models import Family
from app.settings import DEFAULT_SMTP

def get_family_smtp(family_id: int) -> dict:
    with Session(engine) as session:
        family = session.get(Family, family_id)
        if family and family.smtp_config:
            return family.smtp_config
        return DEFAULT_SMTP
