"""Alertas automáticas de seguimiento de propósitos."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser, get_current_user
from app.db.models import Goal, PlanAlert
from app.db.session import get_db

router = APIRouter(prefix="/alerts", tags=["alerts"])


class PlanAlertResponse(BaseModel):
    id: uuid.UUID
    goal_id: uuid.UUID
    goal_name: str
    kind: str
    title: str
    message: str
    period: str
    read_at: datetime | None
    created_at: datetime


@router.get("", response_model=list[PlanAlertResponse])
async def list_alerts(
    unread_only: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[PlanAlertResponse]:
    stmt = (
        select(PlanAlert, Goal.name)
        .join(Goal, PlanAlert.goal_id == Goal.id)
        .where(PlanAlert.user_id == current_user.id)
        .order_by(PlanAlert.created_at.desc())
        .limit(30)
    )
    if unread_only:
        stmt = stmt.where(PlanAlert.read_at.is_(None))
    rows = (await db.execute(stmt)).all()
    return [_response(alert, goal_name) for alert, goal_name in rows]


@router.post("/{alert_id}/read", response_model=PlanAlertResponse)
async def mark_alert_read(
    alert_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> PlanAlertResponse:
    result = await db.execute(
        select(PlanAlert, Goal.name)
        .join(Goal, PlanAlert.goal_id == Goal.id)
        .where(PlanAlert.id == alert_id, PlanAlert.user_id == current_user.id)
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Alerta no encontrada")
    alert, goal_name = row
    alert.read_at = datetime.now(UTC)
    await db.commit()
    return _response(alert, goal_name)


def _response(alert: PlanAlert, goal_name: str) -> PlanAlertResponse:
    return PlanAlertResponse(
        id=alert.id,
        goal_id=alert.goal_id,
        goal_name=goal_name,
        kind=alert.kind,
        title=alert.title,
        message=alert.message,
        period=alert.period,
        read_at=alert.read_at,
        created_at=alert.created_at,
    )
