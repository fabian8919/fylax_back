"""0004 — tabla parser_rules: regex de parseo dinámicas desde la BD

Los patrones de extracción de los parsers deterministas dejan de estar
quemados en app.integrations.gmail.parsers y viven en la tabla
parser_rules (editables en caliente). Incluye la semilla con las reglas
vigentes (Bancolombia, Amazon, BBVA) desde parsers/seed.py.

Revision ID: 0004_parser_rules
Revises: 0003_plan_alerts
Create Date: 2026-11-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.integrations.gmail.parsers.seed import DEFAULT_PARSER_RULES

revision: str = "0004_parser_rules"
down_revision: str | None = "0003_plan_alerts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "parser_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False, unique=True),
        sa.Column("domains", postgresql.ARRAY(sa.String(255)), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("version", sa.String(16), nullable=False, server_default="v1"),
        sa.Column("amount_pattern", sa.Text(), nullable=False),
        sa.Column("merchant_pattern", sa.Text(), nullable=True),
        sa.Column("merchant_static", sa.String(255), nullable=True),
        sa.Column("date_pattern", sa.Text(), nullable=True),
        sa.Column("date_format", sa.String(32), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="COP"),
        sa.Column("payment_method", sa.String(32), nullable=True),
        sa.Column("suggested_category", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    parser_rules = sa.table(
        "parser_rules",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("name", sa.String),
        sa.column("domains", postgresql.ARRAY(sa.String)),
        sa.column("version", sa.String),
        sa.column("amount_pattern", sa.Text),
        sa.column("merchant_pattern", sa.Text),
        sa.column("merchant_static", sa.String),
        sa.column("date_pattern", sa.Text),
        sa.column("date_format", sa.String),
        sa.column("currency", sa.String),
        sa.column("payment_method", sa.String),
        sa.column("suggested_category", sa.String),
    )
    op.bulk_insert(parser_rules, DEFAULT_PARSER_RULES)


def downgrade() -> None:
    op.drop_table("parser_rules")
