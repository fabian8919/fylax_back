"""Dominio goals: propósitos de ahorro del usuario (PRD §9).

GET    /goals                      lista de propósitos del usuario
POST   /goals                      crear propósito (carro, moto, viaje…)
PATCH  /goals/{id}                 editar nombre/monto/icono/color/fecha
POST   /goals/{id}/contributions   abonar al ahorro del propósito
DELETE /goals/{id}                 eliminar

Todo SIEMPRE filtrado por user_id (multitenant — PRD §8).
"""

import uuid
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser, get_current_user
from app.db.models import Goal
from app.db.session import get_db

router = APIRouter(prefix="/goals", tags=["goals"])


class GoalCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    target_amount: Decimal = Field(gt=0)
    icon: str = Field(default="savings", max_length=64)
    color: str = Field(default="#2E8FFF", max_length=9)
    deadline: datetime | None = None


class GoalUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=160)
    target_amount: Decimal | None = Field(None, gt=0)
    icon: str | None = Field(None, max_length=64)
    color: str | None = Field(None, max_length=9)
    deadline: datetime | None = None


class ContributionCreate(BaseModel):
    amount: Decimal = Field(gt=0)


class GoalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    target_amount: Decimal
    saved_amount: Decimal
    icon: str
    color: str
    deadline: datetime | None
    created_at: datetime


@router.get("", response_model=list[GoalResponse])
async def list_goals(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[Goal]:
    result = await db.execute(
        select(Goal)
        .where(Goal.user_id == current_user.id)
        .order_by(Goal.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("", response_model=GoalResponse, status_code=status.HTTP_201_CREATED)
async def create_goal(
    body: GoalCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> Goal:
    goal = Goal(
        user_id=current_user.id,
        name=body.name.strip(),
        target_amount=body.target_amount,
        icon=body.icon,
        color=body.color,
        deadline=body.deadline,
    )
    db.add(goal)
    await db.commit()
    await db.refresh(goal)
    return goal


@router.patch("/{goal_id}", response_model=GoalResponse)
async def update_goal(
    goal_id: uuid.UUID,
    body: GoalUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> Goal:
    goal = await _get_own_goal(db, current_user.id, goal_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(goal, field, value)
    await db.commit()
    await db.refresh(goal)
    return goal


@router.post("/{goal_id}/contributions", response_model=GoalResponse)
async def add_contribution(
    goal_id: uuid.UUID,
    body: ContributionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> Goal:
    """Abona al ahorro: saved_amount += amount (Decimal, nunca float)."""
    goal = await _get_own_goal(db, current_user.id, goal_id)
    goal.saved_amount = goal.saved_amount + body.amount
    await db.commit()
    await db.refresh(goal)
    return goal


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_goal(
    goal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> None:
    await _get_own_goal(db, current_user.id, goal_id)
    await db.execute(
        delete(Goal).where(Goal.id == goal_id, Goal.user_id == current_user.id)
    )
    await db.commit()


async def _get_own_goal(
    db: AsyncSession, user_id: uuid.UUID, goal_id: uuid.UUID
) -> Goal:
    result = await db.execute(
        select(Goal).where(Goal.id == goal_id, Goal.user_id == user_id)
    )
    goal = result.scalar_one_or_none()
    if goal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Propósito no encontrado")
    return goal
