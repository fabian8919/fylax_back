"""0002 — captura de ingreso mensual/quincenal para planes financieros

Revision ID: 0002_income_planning
Revises: 0001_initial
Create Date: 2026-10-28
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_income_planning"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("income_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "users",
        sa.Column(
            "income_frequency",
            sa.String(16),
            nullable=False,
            server_default="monthly",
        ),
    )
    # Usuarios existentes: su ingreso mensual ya configurado pasa a ser el
    # monto del período, sin cambiar el equivalente mensual.
    op.execute("UPDATE users SET income_amount = monthly_income")


def downgrade() -> None:
    op.drop_column("users", "income_frequency")
    op.drop_column("users", "income_amount")
