"""Dominio sync: GET /sync/status (PRD §9, F3.4).

Estado de la sincronización de correo: última actualización, historyId
procesado y estado del watch (active | error | revoked — PRD §8).
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser, get_current_user
from app.db.models import EmailSyncState
from app.db.session import get_db

router = APIRouter(tags=["sync"])


class SyncStatusResponse(BaseModel):
    status: str
    last_sync_at: datetime | None
    gmail_history_id: str | None
    last_error: str | None = None


@router.get("/sync/status", response_model=SyncStatusResponse)
async def get_sync_status(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> SyncStatusResponse:
    result = await db.execute(
        select(EmailSyncState).where(EmailSyncState.user_id == current_user.id)
    )
    state = result.scalar_one_or_none()
    if state is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Sin estado de sincronización"
        )
    return SyncStatusResponse(
        status=state.status,
        last_sync_at=state.last_sync_at,
        gmail_history_id=state.gmail_history_id,
        last_error=state.last_error,
    )
