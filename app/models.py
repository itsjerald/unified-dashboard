from sqlmodel import SQLModel, Field, Column, JSON, Relationship
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
    # ✅ NEW: family and parent
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
    created_at: datetime = Field(default_factory=datetime.utcnow)
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
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Category(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str

class MerchantRule(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    pattern: str    # text pattern to match
    category_id: int = Field(foreign_key="category.id")


class Family(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, nullable=False, unique=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    members: List["User"] = Relationship(back_populates="family")

class TxnShareRequest(SQLModel):
    txn_ids: List[int]

class DeletionRequest(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    entity_type: str  # "user" or "family"
    entity_id: int
    requested_by_id: int = Field(foreign_key="user.id")
    approval_ids: List[int] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    executed: bool = Field(default=False)
