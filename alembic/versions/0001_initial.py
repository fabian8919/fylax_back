"""0001 — esquema inicial + semilla de categorías

Crea las tablas users, categories, transactions, email_sync_state y
goals (PRD §8), con:

- UNIQUE (user_id, source_ref_id) en transactions → idempotencia de la
  ingesta (PRD §F2.6).
- Índice (user_id, date) para las consultas del dashboard.
- Semilla de categorías del sistema alineada con la app Flutter.

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.categories.seed import DEFAULT_CATEGORIES

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False, server_default=""),
        sa.Column("google_refresh_token", sa.Text(), nullable=True),
        sa.Column(
            "subscription_tier", sa.String(16), nullable=False, server_default="free"
        ),
        sa.Column("wompi_customer_id", sa.String(128), nullable=True),
        sa.Column(
            "monthly_income",
            sa.Numeric(12, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "monthly_budget",
            sa.Numeric(12, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("icon", sa.String(64), nullable=False, server_default="category"),
        sa.Column("color", sa.String(9), nullable=False, server_default="#888888"),
        sa.Column("type", sa.String(16), nullable=False, server_default="expense"),
        sa.Column("is_system_default", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_categories_user_id", "categories", ["user_id"])

    op.create_table(
        "transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "category_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("categories.id"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="COP"),
        sa.Column("date", sa.DateTime(), nullable=False),
        sa.Column("merchant_clean", sa.String(255), nullable=False),
        sa.Column("source", sa.String(16), nullable=False, server_default="manual"),
        sa.Column("source_ref_id", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "source_ref_id", name="uq_tx_user_source_ref"),
    )
    op.create_index("ix_transactions_user_id", "transactions", ["user_id"])
    op.create_index("ix_transactions_user_date", "transactions", ["user_id", "date"])

    op.create_table(
        "email_sync_state",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            primary_key=True,
        ),
        sa.Column("gmail_history_id", sa.String(32), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("last_error", sa.Text(), nullable=True),
    )

    op.create_table(
        "goals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("target_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "saved_amount", sa.Numeric(12, 2), nullable=False, server_default="0"
        ),
        sa.Column("icon", sa.String(64), nullable=False, server_default="savings"),
        sa.Column("color", sa.String(9), nullable=False, server_default="#2E8FFF"),
        sa.Column("deadline", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_goals_user_id", "goals", ["user_id"])

    # Semilla de categorías del sistema (user_id NULL = globales).
    categories = sa.table(
        "categories",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("user_id", postgresql.UUID(as_uuid=True)),
        sa.column("name", sa.String),
        sa.column("icon", sa.String),
        sa.column("color", sa.String),
        sa.column("type", sa.String),
        sa.column("is_system_default", sa.Boolean),
    )
    op.bulk_insert(
        categories,
        [
            {
                "id": c["id"],
                "user_id": None,
                "name": c["name"],
                "icon": c["icon"],
                "color": c["color"],
                "type": c["type"],
                "is_system_default": True,
            }
            for c in DEFAULT_CATEGORIES
        ],
    )


def downgrade() -> None:
    op.drop_table("goals")
    op.drop_table("email_sync_state")
    op.drop_index("ix_transactions_user_date", table_name="transactions")
    op.drop_index("ix_transactions_user_id", table_name="transactions")
    op.drop_table("transactions")
    op.drop_index("ix_categories_user_id", table_name="categories")
    op.drop_table("categories")
    op.drop_table("users")
