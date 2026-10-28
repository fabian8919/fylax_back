"""Dominio users: POST /auth/session (PRD §9).

Registra/actualiza al usuario en la base de datos a partir del JWT de
Supabase Auth, que incluye los tokens de Google. El provider_token
(refresh_token de Google) se almacena cifrado con AES-256-GCM (PRD §F1.3).
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser, get_current_user, get_token_cipher
from app.db.models import EmailSyncState, User
from app.db.session import get_db

router = APIRouter(tags=["auth"])


class SessionRequest(BaseModel):
    """Lo que el cliente envía tras el OAuth de Supabase."""

    # provider_token de Supabase = refresh_token de Google. Viaja UNA vez
    # por HTTPS y se descarta del lado cliente tras el registro.
    google_refresh_token: str | None = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    name: str
    subscription_tier: str
    # Ingreso tal como lo recibe el usuario y equivalente mensual usado por
    # presupuesto, dashboard y planes de acción.
    income_amount: Decimal
    income_frequency: Literal["monthly", "biweekly"]
    monthly_income: Decimal
    monthly_budget: Decimal
    created_at: datetime


class UserUpdate(BaseModel):
    """PATCH /users/me — perfil y configuración financiera.

    income_amount es el valor de cada nómina: monthly = una al mes;
    biweekly = dos al mes. monthly_income se conserva como compatibilidad
    para clientes antiguos, pero el ingreso por período tiene prioridad.
    """

    name: str | None = Field(None, max_length=255)
    income_amount: Decimal | None = Field(None, ge=0)
    income_frequency: Literal["monthly", "biweekly"] | None = None
    monthly_income: Decimal | None = Field(None, ge=0)
    monthly_budget: Decimal | None = Field(None, ge=0)


@router.post("/auth/session", response_model=UserResponse)
async def create_or_update_session(
    body: SessionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    cipher=Depends(get_token_cipher),
) -> User:
    """F1.1/F1.3 — upsert del usuario + persistencia cifrada del refresh token."""
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            id=current_user.id,
            email=current_user.email,
            google_refresh_token=(
                cipher.encrypt(body.google_refresh_token) if body.google_refresh_token else None
            ),
        )
        db.add(user)
        # Flush explícito: sin relationship ORM entre User y EmailSyncState
        # el unit of work no garantiza el orden de inserción y el hijo
        # puede insertarse antes que el padre (violación de FK → 500).
        await db.flush()
        db.add(EmailSyncState(user_id=user.id, status="active"))
    else:
        user.email = current_user.email
        if body.google_refresh_token:
            # Rotación del token: se re-cifra y se reemplaza.
            user.google_refresh_token = cipher.encrypt(body.google_refresh_token)

    await db.commit()
    await db.refresh(user)
    return user


@router.get("/users/me", response_model=UserResponse)
async def get_me(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> User:
    """Perfil del usuario autenticado."""
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="Usuario no registrado: llama primero a /auth/session",
        )
    return user


@router.patch("/users/me", response_model=UserResponse)
async def update_me(
    body: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> User:
    """Actualiza perfil, ingreso por período y presupuesto mensual."""
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="Usuario no registrado: llama primero a /auth/session",
        )

    data = body.model_dump(exclude_unset=True)
    for field in ("name", "monthly_budget"):
        if field in data:
            setattr(user, field, data[field])

    if "income_amount" in data or "income_frequency" in data:
        if "income_amount" in data:
            user.income_amount = data["income_amount"]
        if "income_frequency" in data:
            user.income_frequency = data["income_frequency"]
        # Migra suavemente perfiles antiguos que solo tenían monthly_income.
        if user.income_amount == 0 and user.monthly_income > 0:
            divisor = 2 if user.income_frequency == "biweekly" else 1
            user.income_amount = user.monthly_income / divisor
        multiplier = 2 if user.income_frequency == "biweekly" else 1
        user.monthly_income = user.income_amount * multiplier
    elif "monthly_income" in data:
        # Compatibilidad con el cliente anterior.
        user.monthly_income = data["monthly_income"]
        divisor = 2 if user.income_frequency == "biweekly" else 1
        user.income_amount = user.monthly_income / divisor

    await db.commit()
    await db.refresh(user)
    return user
