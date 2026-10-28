"""Seguimiento automático de planes a partir de los movimientos reales."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Category, CategoryType, Goal, PlanAlert, Transaction, User
from app.goals.planner import build_goal_action_plan

_ZERO = Decimal("0")


async def get_monthly_spent(
    db: AsyncSession, user_id: uuid.UUID, now: datetime | None = None
) -> Decimal:
    """Suma los gastos del mes; los ingresos y aportes no cuentan como gasto."""
    current = now or datetime.now(UTC)
    month_start = current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    value = (
        await db.execute(
            select(func.coalesce(func.sum(Transaction.amount), 0))
            .join(Category, Transaction.category_id == Category.id)
            .where(
                Transaction.user_id == user_id,
                Transaction.date >= month_start,
                Category.type == CategoryType.expense.value,
            )
        )
    ).scalar_one()
    return Decimal(value)


async def sync_plan_alerts(
    db: AsyncSession, user_id: uuid.UUID, now: datetime | None = None
) -> list[PlanAlert]:
    """Genera una sola alerta por propósito, severidad y mes.

    Se llama después de insertar un movimiento manual o uno procesado desde
    Gmail. No hace commit: forma parte de la transacción de quien la invoca.
    """
    current = now or datetime.now(UTC)
    user = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if user is None or user.monthly_income <= 0:
        return []

    goals = list(
        (
            await db.execute(
                select(Goal).where(
                    Goal.user_id == user_id,
                    Goal.saved_amount < Goal.target_amount,
                )
            )
        )
        .scalars()
        .all()
    )
    if not goals:
        return []

    spent = await get_monthly_spent(db, user_id, current)
    period = current.strftime("%Y-%m")
    created: list[PlanAlert] = []
    for goal in goals:
        plan = build_goal_action_plan(
            goal,
            user,
            active_goals=len(goals),
            today=current.date(),
            monthly_spent=spent,
        )
        if plan.status == "on_track" or plan.alert_message is None:
            continue

        kind = f"plan_{plan.status}"
        existing = (
            await db.execute(
                select(PlanAlert.id).where(
                    PlanAlert.user_id == user_id,
                    PlanAlert.goal_id == goal.id,
                    PlanAlert.kind == kind,
                    PlanAlert.period == period,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            continue

        alert = PlanAlert(
            user_id=user_id,
            goal_id=goal.id,
            kind=kind,
            title=(
                f"{goal.name} está en riesgo"
                if plan.status == "at_risk"
                else f"El plan de {goal.name} se está desviando"
            ),
            message=plan.alert_message,
            period=period,
        )
        db.add(alert)
        created.append(alert)
    return created
