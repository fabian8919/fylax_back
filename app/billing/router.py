"""Dominio billing (Épica 4 — preparación SaaS con Wompi, sin paywall).

El middleware de límites por tier (PRD §F4.1) vive aquí; el esquema ya
tiene subscription_tier y wompi_customer_id (PRD §F4.2). El webhook de
eventos de Wompi se agregará en una fase posterior poblando campos
existentes, sin migraciones destructivas.
"""

from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import TierLimitExceededError
from app.core.security import CurrentUser, get_current_user
from app.db.models import Transaction, User
from app.db.session import get_db

router = APIRouter(prefix="/billing", tags=["billing"])

# Cupo mensual del tier free en correos procesados (PRD §F4.1).
FREE_TIER_MONTHLY_EMAIL_LIMIT = 500


class BillingStatus(BaseModel):
    subscription_tier: str
    wompi_customer_id: str | None


@router.get("/status", response_model=BillingStatus)
async def get_billing_status(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BillingStatus:
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one()
    return BillingStatus(
        subscription_tier=user.subscription_tier,
        wompi_customer_id=user.wompi_customer_id,
    )


async def enforce_tier_limits(
    db: AsyncSession, user: User, emails_this_month: int
) -> None:
    """Middleware de límites: el tier free procesa hasta N correos/mes."""
    if (
        user.subscription_tier == "free"
        and emails_this_month >= FREE_TIER_MONTHLY_EMAIL_LIMIT
    ):
        raise TierLimitExceededError(
            "Límite del plan gratuito alcanzado. Mejora a Pro para continuar."
        )
