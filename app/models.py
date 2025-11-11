from sqlmodel import SQLModel, Field, Column, JSON
from typing import Optional, List
from datetime import datetime

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, nullable=False, unique=True)
    password_hash: str
    totp_secret: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    role: str = Field(default="user")
    first_login: bool = Field(default=True)


class Transaction(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key='user.id')
    txn_id: Optional[str] = None
    txn_hash: str = Field(index=True, nullable=False, unique=True)
    date: datetime
    amount: float
    merchant: Optional[str] = None
    note: Optional[str] = None
    paid: bool = False
    week_paid: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    category: str = Field(default="Other")


class Payment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    payer_id: int
    payee_id: int
    amount: float
    txn_refs: List[int] = Field(sa_column=Column(JSON), default=[])
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Category(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str

class MerchantRule(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    pattern: str    # text pattern to match
    category_id: int = Field(foreign_key="category.id")
