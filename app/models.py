from sqlmodel import SQLModel, Field, Column, JSON, Relationship
from typing import Optional, List
from datetime import datetime, timezone, timedelta


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, nullable=False, unique=True)
    password_hash: str
    totp_secret: Optional[str] = None
    verification_token: Optional[str] = Field(default=None, index=True)
    verification_expires_at: datetime = Field(default_factory=lambda: datetime.utcnow() + timedelta(days=7))
    is_verified: bool = Field(default=False)
    smtp_config: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    role: str = Field(default="user")
    first_login: bool = Field(default=True)
    family_id: Optional[int] = Field(default=None, foreign_key="family.id")
    parent_id: Optional[int] = Field(default=None, foreign_key="user.id")

    family: Optional["Family"] = Relationship(back_populates="members")
    parent: Optional["User"] = Relationship(
        back_populates="children",
        sa_relationship_kwargs={"remote_side": "User.id"}
    )
    children: List["User"] = Relationship(
        back_populates="parent",
        sa_relationship_kwargs={"cascade": "all,delete"}
    )
    transactions: List["Transaction"] = Relationship(back_populates="user")


class Transaction(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    family_id: int = Field(foreign_key="family.id")
    txn_id: Optional[str] = None
    txn_hash: str = Field(index=True, nullable=False, unique=True)
    date: datetime
    amount: float
    merchant: Optional[str] = None
    note: Optional[str] = None
    paid: bool = False
    week_paid: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    category: str = Field(default="Other")
    type: str  # debit or credit
    description: str
    shared: bool = False
    marked_for_deletion: bool = Field(default=False)

    user: User = Relationship(back_populates="transactions")


class Payment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    payer_id: int
    payee_id: int
    amount: float
    txn_refs: List[int] = Field(sa_column=Column(JSON), default=[])
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Category(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    family_id: Optional[int] = Field(default=None, foreign_key="family.id")
    family: Optional["Family"] = Relationship(back_populates="categories")

class MerchantRule(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    pattern: str    # text pattern to match
    category_id: int = Field(foreign_key="category.id")


class Family(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, nullable=False, unique=True)
    smtp_config: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relationships
    members: List["User"] = Relationship(back_populates="family")
    categories: List["Category"] = Relationship(back_populates="family")

class TxnShareRequest(SQLModel):
    txn_ids: List[int]

class DeletionRequest(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    entity_type: str  # "user" or "family"
    entity_id: int
    requested_by_id: int = Field(foreign_key="user.id")
    approval_ids: List[int] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    executed: bool = Field(default=False)

class VerificationResendLog(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    email: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))