"""0006 — parser_rules: subject_pattern + priority, familia de reglas BBVA

- Columnas nuevas: subject_pattern (filtro por asunto: la regla solo se
  intenta si el asunto coincide → los correos de marketing del banco ya
  no se parsean como transacciones) y priority (orden de intento cuando
  un dominio tiene varias reglas).
- Reemplaza la regla única "bbva" por una familia por tipo de
  movimiento (compra, retiro, transferencias, transferencia en camino,
  PSE, facturas, Bre-B), con merchant_pattern apuntando al campo real
  de cada plantilla (Establecimiento / beneficiario / llave / factura).
- Incluye el dominio bbvanet.com.co (remitente real de las alertas).

Revision ID: 0006_parser_rule_subjects
Revises: 0005_app_settings
Create Date: 2026-11-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.integrations.gmail.parsers.seed import DEFAULT_PARSER_RULES

revision: str = "0006_parser_rule_subjects"
down_revision: str | None = "0005_app_settings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Fila bbva anterior a 0006 (para downgrade).
_OLD_BBVA = {
    "id": "00000000-0000-4000-8000-000000000103",
    "name": "bbva",
    "domains": ["bbva.com.co", "bbva.com"],
    "version": "v1",
    "amount_pattern": r"\$\s*([\d.,]+)",
    "merchant_pattern": r"(?i)en\s+([A-Za-z0-9 &'.-]+?)(?:\s+el\s|\s+con\s|\.\s|\s*$)",
    "merchant_static": None,
    "date_pattern": r"(\d{2}/\d{2}/\d{4})",
    "date_format": "%d/%m/%Y",
    "currency": "COP",
    "payment_method": None,
    "suggested_category": None,
}

_BBVA_FAMILY = [r for r in DEFAULT_PARSER_RULES if r["name"].startswith("bbva")]


def _table() -> sa.Table:
    return sa.table(
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
        sa.column("subject_pattern", sa.Text),
        sa.column("priority", sa.Integer),
        sa.column("currency", sa.String),
        sa.column("payment_method", sa.String),
        sa.column("suggested_category", sa.String),
    )


def upgrade() -> None:
    op.add_column("parser_rules", sa.Column("subject_pattern", sa.Text(), nullable=True))
    op.add_column(
        "parser_rules",
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
    )

    op.execute("DELETE FROM parser_rules WHERE name = 'bbva'")
    op.bulk_insert(_table(), _BBVA_FAMILY)


def downgrade() -> None:
    op.execute("DELETE FROM parser_rules WHERE name LIKE 'bbva\\_%'")
    op.bulk_insert(_table(), [_OLD_BBVA])

    op.drop_column("parser_rules", "priority")
    op.drop_column("parser_rules", "subject_pattern")
