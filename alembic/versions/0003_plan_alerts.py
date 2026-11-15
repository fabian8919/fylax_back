"""0003 — alertas automáticas de seguimiento de planes

Revision ID: 0003_plan_alerts
Revises: 0002_income_planning
Create Date: 2026-10-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003_plan_alerts"
down_revision: str | None = "0002_income_planning"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "plan_alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("goal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("period", sa.String(7), nullable=False),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["goal_id"], ["goals.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "user_id", "goal_id", "kind", "period", name="uq_plan_alert_period"
        ),
    )
    op.create_index("ix_plan_alerts_user_id", "plan_alerts", ["user_id"])
    op.create_index(
        "ix_plan_alerts_user_created", "plan_alerts", ["user_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_plan_alerts_user_created", table_name="plan_alerts")
    op.drop_index("ix_plan_alerts_user_id", table_name="plan_alerts")
    op.drop_table("plan_alerts")
