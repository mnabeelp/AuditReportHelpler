"""SQLModel database models for Audit Report Helper."""
import json
from datetime import datetime, timezone
from typing import Optional, List
from sqlmodel import SQLModel, Field


class CompanyProfile(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    authorized_spenders: str = Field(default="[]")  # JSON list of names
    owners: str = Field(default="[]")  # JSON list of {name, type}
    cards: str = Field(default="[]")  # JSON list of last-4
    equity_mode: str = Field(default="single")  # single | multi
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def spenders_list(self) -> List[str]:
        return json.loads(self.authorized_spenders or "[]")

    def owners_list(self) -> List[dict]:
        return json.loads(self.owners or "[]")

    def cards_list(self) -> List[str]:
        return json.loads(self.cards or "[]")


class Document(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = Field(default="processed")  # processed | deleted
    entry_count: int = Field(default=0)


class Transaction(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    document_id: Optional[int] = Field(default=None, foreign_key="document.id")
    date: Optional[str] = None
    vendor: Optional[str] = None
    doc_number: Optional[str] = None
    description: Optional[str] = None
    account: Optional[str] = None
    amount: Optional[float] = None
    tax: Optional[float] = 0
    currency: Optional[str] = "USD"
    payment_mode: Optional[str] = None
    paid_through: Optional[str] = None
    notes: Optional[str] = None
    account_holder_name: Optional[str] = None
    card_last4: Optional[str] = None
    classification: str = Field(default="unknown")  # company/personal/owner/unknown
    confidence: Optional[float] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Verification(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    transaction_id: int = Field(foreign_key="transaction.id")
    original_classification: str
    overridden_classification: Optional[str] = None
    overridden_by: Optional[str] = None
    overridden_at: Optional[datetime] = None
    note: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Export(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    document_id: Optional[int] = Field(default=None, foreign_key="document.id")
    format: str
    file_path: str
    exported_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuditLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    action: str
    entity: str
    entity_id: Optional[int] = None
    detail: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
