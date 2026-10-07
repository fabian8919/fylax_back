"""Dominio dashboard: GET /dashboard/summary (PRD §9, F3.1).

Balance del mes, gasto por categoría y presupuesto restante. Consultas
agregadas sobre transactions SIEMPRE filtradas por user_id (multitenant —
PRD §8).
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser, get_current_user
from app.db.models import Category, Transaction
from app.db.session import get_db

router = APIRouter(tags=["dashboard"])


class CategorySpending(BaseModel):
    category_id: uuid.UUID
    category_name: str
    amount: Decimal
    icon: str
    color: str


class DashboardSummary(BaseModel):
    month_balance: Decimal
    available_budget: Decimal
    spending_by_category: list[CategorySpending]


@router.get("/dashboard/summary", response_model=DashboardSummary)
async def get_summary(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> DashboardSummary:
    now = datetime.now(UTC)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    rows = (
        await db.execute(
            select(
                Category.id,
                Category.name,
                Category.icon,
                Category.color,
                func.coalesce(func.sum(Transaction.amount), 0).label("total"),
            )
            .join(Transaction, Transaction.category_id == Category.id)
            .where(
                Transaction.user_id == current_user.id,
                Transaction.date >= month_start,
                Transaction.amount < 0,  # gastos (signo negativo = egreso)
            )
            .group_by(Category.id)
            .order_by(func.sum(Transaction.amount).asc())
        )
    ).all()

    total_spent = sum((r.total for r in rows), Decimal("0"))
    # TODO(Fase 4): available_budget = presupuesto mensual del usuario
    # (tabla de presupuestos o campo en users) menos total_spent.
    available_budget = Decimal("0") - total_spent

    return DashboardSummary(
        month_balance=-total_spent,
        available_budget=available_budget,
        spending_by_category=[
            CategorySpending(
                category_id=r.id,
                category_name=r.name,
                amount=-r.total,
                icon=r.icon,
                color=r.color,
            )
            for r in rows
        ],
    )
