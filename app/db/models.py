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
from sqlalchemy.dialects.postgresql import ARRAY, UUID
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
    # Configuración financiera del usuario (dashboard F3.1). Montos
    # positivos; 0 = no configurado.
    monthly_income: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    monthly_budget: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    # Ingreso por período (0002): monto declarado y su frecuencia. El
    # equivalente mensual sigue en monthly_income.
    income_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    income_frequency: Mapped[str] = mapped_column(String(16), default="monthly")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # NULL = categoría del sistema (semilla); con valor = personalizada
    # del usuario (solo visible para él).
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
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
    # Último error de sincronización (truncado); NULL cuando va bien.
    last_error: Mapped[str | None] = mapped_column(Text)


class Goal(Base):
    """Propósito de ahorro del usuario (carro, moto, viaje, deudas…)."""

    __tablename__ = "goals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    target_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    saved_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    icon: Mapped[str] = mapped_column(String(64), default="savings")
    color: Mapped[str] = mapped_column(String(9), default="#2E8FFF")
    deadline: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ParserRule(Base):
    """Regla de parseo de correos por remitente (0004_parser_rules).

    Las regex de extracción viven aquí (editables en caliente desde la
    BD) en vez de quemadas en código. Semilla: parsers/seed.py.
    Los montos se asumen en formato COP ("." miles, "," decimales).
    """

    __tablename__ = "parser_rules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Identificador del remitente (bancolombia, amazon…), único.
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    # Dominios del remitente que esta regla sabe procesar.
    domains: Mapped[list[str]] = mapped_column(ARRAY(String(255)), nullable=False)
    enabled: Mapped[bool] = mapped_column(default=True)
    # Versión de la regla: los bancos cambian plantillas (PRD §13).
    version: Mapped[str] = mapped_column(String(16), default="v1")
    # Regex con el monto en el grupo 1 (obligatoria).
    amount_pattern: Mapped[str] = mapped_column(Text, nullable=False)
    # Regex con el comercio en el grupo 1; NULL si merchant_static.
    merchant_pattern: Mapped[str | None] = mapped_column(Text)
    # Comercio fijo (p. ej. "Amazon") cuando no se extrae del cuerpo.
    merchant_static: Mapped[str | None] = mapped_column(String(255))
    # Regex con la fecha completa en el grupo 1 + formato strptime.
    date_pattern: Mapped[str | None] = mapped_column(Text)
    date_format: Mapped[str | None] = mapped_column(String(32))
    currency: Mapped[str] = mapped_column(String(3), default="COP")
    payment_method: Mapped[str | None] = mapped_column(String(32))
    suggested_category: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class AppSetting(Base):
    """Configuración dinámica clave/valor (0005_app_settings).

    Parámetros operativos editables en caliente sin redespliegue
    (p. ej. gmail_financial_query). Semilla: app/core/db_settings.py.
    """

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(String(255), default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class PlanAlert(Base):
    """Alerta automática de seguimiento de un propósito (0003_plan_alerts).

    La unique (user_id, goal_id, kind, period) hace idempotente al
    monitor: una alerta por tipo y período aunque se evalúe varias veces.
    """

    __tablename__ = "plan_alerts"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "goal_id", "kind", "period", name="uq_plan_alert_period"
        ),
        Index("ix_plan_alerts_user_created", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    goal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("goals.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    period: Mapped[str] = mapped_column(String(7), nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
