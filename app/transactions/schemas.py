"""Pydantic schemas de transactions (DTO estricto — PRD §5.2)."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TransactionBase(BaseModel):
    category_id: UUID
    amount: Decimal
    currency: str = "COP"
    merchant_clean: str


class TransactionCreate(TransactionBase):
    """POST /transactions — transacción manual (efectivo u otros)."""

    date: datetime


class TransactionUpdate(BaseModel):
    """PATCH /transactions/{id} — edita monto, categoría o comercio."""

    category_id: UUID | None = None
    amount: Decimal | None = None
    merchant_clean: str | None = None


class TransactionResponse(TransactionBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    date: datetime
    source: str
    source_ref_id: str | None
    created_at: datetime
