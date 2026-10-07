"""Dominio dashboard: GET /dashboard/summary (PRD §9, F3.1).

Balance del mes, gasto por categoría y presupuesto restante. Consultas
agregadas sobre transactions SIEMPRE filtradas por user_id (multitenant —
PRD §8).

Convención de montos: POSITIVOS siempre. Egreso vs. ingreso se distingue
por Category.type ("expense" | "income"), no por el signo — la app
Flutter envía montos absolutos.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser, get_current_user
from app.db.models import Category, CategoryType, Transaction, User
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

    # Gasto del mes por categoría (solo categorías tipo expense).
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
                Category.type == CategoryType.expense.value,
            )
            .group_by(Category.id)
            .order_by(func.sum(Transaction.amount).desc())
        )
    ).all()

    # Ingresos registrados del mes (categorías tipo income).
    income_registered = (
        await db.execute(
            select(func.coalesce(func.sum(Transaction.amount), 0))
            .join(Category, Transaction.category_id == Category.id)
            .where(
                Transaction.user_id == current_user.id,
                Transaction.date >= month_start,
                Category.type == CategoryType.income.value,
            )
        )
    ).scalar_one()

    # Ingreso/presupuesto de referencia: lo configurado en el perfil;
    # si no está, se deriva de los movimientos.
    user = (
        await db.execute(select(User).where(User.id == current_user.id))
    ).scalar_one_or_none()

    total_spent = sum((r.total for r in rows), Decimal("0"))
    income = (
        user.monthly_income
        if user is not None and user.monthly_income > 0
        else Decimal(income_registered)
    )
    budget = (
        user.monthly_budget
        if user is not None and user.monthly_budget > 0
        else Decimal(total_spent)
    )

    return DashboardSummary(
        month_balance=income - total_spent,
        available_budget=budget - total_spent,
        spending_by_category=[
            CategorySpending(
                category_id=r.id,
                category_name=r.name,
                amount=r.total,
                icon=r.icon,
                color=r.color,
            )
            for r in rows
        ],
    )
