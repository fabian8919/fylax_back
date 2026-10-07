"""Modelos SQLAlchemy (PRD §8 — modelo de base de datos).

Montos en Numeric(10,2) (Decimal — nunca float para dinero), currency en
ISO 4217, y la restricción UNIQUE (user_id, source_ref_id) que garantiza
la idempotencia de la ingesta (PRD §F2.6).
"""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class SubscriptionTier(StrEnum):
    free = "free"
    pro = "pro"


class TransactionSource(StrEnum):
    manual = "manual"
    gmail_api = "gmail_api"


class CategoryType(StrEnum):
    income = "income"
    expense = "expense"


class SyncStatusState(StrEnum):
    active = "active"
    error = "error"
    revoked = "revoked"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Enlazado a Supabase Auth; el email es único.
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), default="")
    # AES-256-GCM (PRD §F1.3). El token NUNCA está en texto plano.
    google_refresh_token: Mapped[str | None] = mapped_column(Text)
    subscription_tier: Mapped[str] = mapped_column(
        String(16), default=SubscriptionTier.free.value
    )
    # Preparación futura Wompi (PRD §F4.2) — sin migraciones destructivas.
    wompi_customer_id: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    icon: Mapped[str] = mapped_column(String(64), default="category")
    color: Mapped[str] = mapped_column(String(9), default="#888888")
    type: Mapped[str] = mapped_column(String(16), default=CategoryType.expense.value)
    is_system_default: Mapped[bool] = mapped_column(default=True)


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        # Idempotencia: procesar el mismo correo dos veces jamás
        # duplica el gasto (PRD §F2.6). Para transacciones manuales,
        # source_ref_id queda en NULL y la restricción no aplica.
        UniqueConstraint("user_id", "source_ref_id", name="uq_tx_user_source_ref"),
        Index("ix_transactions_user_date", "user_id", "date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id"), nullable=False
    )
    # Decimal(10,2) — PRD §8.
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="COP")
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # Comercio ya limpio por el parser / JEV.
    merchant_clean: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(
        String(16), default=TransactionSource.manual.value
    )
    source_ref_id: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    category: Mapped[Category] = relationship()


class EmailSyncState(Base):
    __tablename__ = "email_sync_state"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True
    )
    # Último historyId procesado: lectura incremental (PRD §F2.2).
    gmail_history_id: Mapped[str | None] = mapped_column(String(32))
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(
        String(16), default=SyncStatusState.active.value
    )
