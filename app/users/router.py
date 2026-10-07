"""Dominio users: POST /auth/session (PRD §9).

Registra/actualiza al usuario en la base de datos a partir del JWT de
Supabase Auth, que incluye los tokens de Google. El provider_token
(refresh_token de Google) se almacena cifrado con AES-256-GCM (PRD §F1.3).
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, EmailStr
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
    created_at: datetime


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
                cipher.encrypt(body.google_refresh_token)
                if body.google_refresh_token
                else None
            ),
        )
        db.add(user)
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
async def get_me(current_user: CurrentUser = Depends(get_current_user)) -> User:
    # TODO(Fase 4): consultar el usuario real en BD y devolverlo.
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED)
