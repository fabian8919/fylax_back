"""0005 — tabla app_settings: configuración dinámica clave/valor

Mueve la query de búsqueda financiera de Gmail (fallback cuando el
historyId expira, PRD §F2.2) del código a la BD, como clave
gmail_financial_query editable en caliente.

Revision ID: 0005_app_settings
Revises: 0004_parser_rules
Create Date: 2026-11-23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.core.db_settings import DEFAULT_SETTINGS

revision: str = "0005_app_settings"
down_revision: str | None = "0004_parser_rules"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DESCRIPTIONS = {
    "gmail_financial_query": (
        "Query de búsqueda de Gmail para la re-sincronización cuando el "
        "historyId expira (fallback, PRD §F2.2)"
    ),
}


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(128), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("description", sa.String(255), nullable=False, server_default=""),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    app_settings = sa.table(
        "app_settings",
        sa.column("key", sa.String),
        sa.column("value", sa.Text),
        sa.column("description", sa.String),
    )
    op.bulk_insert(
        app_settings,
        [
            {
                "key": key,
                "value": value,
                "description": _DESCRIPTIONS.get(key, ""),
            }
            for key, value in DEFAULT_SETTINGS.items()
        ],
    )


def downgrade() -> None:
    op.drop_table("app_settings")
