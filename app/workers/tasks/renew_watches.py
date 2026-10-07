"""Renovación diaria de los watches de Gmail (PRD §F2.1, §13).

El watch de la Gmail API expira a los 7 días; esta tarea (Celery beat,
una vez al día) itera los usuarios con google_refresh_token y renueva
cada watch. Un fallo individual NO detiene el lote: se marca el estado
de sync del usuario y se continúa con el siguiente.
"""

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.security import TokenCipher
from app.db.models import EmailSyncState, SyncStatusState, User
from app.integrations.gmail.watch import register_watch
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task
def renew_gmail_watches() -> dict:
    """Renueva el watch de todos los usuarios con Gmail conectado."""
    return asyncio.run(_renew_all())


async def _renew_all() -> dict:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    renewed, failed = 0, 0
    try:
        async with session_factory() as db:
            users = (
                (
                    await db.execute(
                        select(User).where(User.google_refresh_token.is_not(None))
                    )
                )
                .scalars()
                .all()
            )
            cipher = TokenCipher(settings.token_encryption_key)

            for user in users:
                try:
                    # Descifrado solo en memoria, nunca en logs (F1.3).
                    refresh_token = cipher.decrypt(user.google_refresh_token)
                    register_watch(
                        refresh_token,
                        project_id=settings.gcp_project_id,
                        topic=settings.pubsub_topic,
                    )
                    renewed += 1
                except Exception as exc:  # noqa: BLE001 — lote resiliente
                    failed += 1
                    logger.exception("No se renovó el watch de %s", user.email)
                    state = (
                        await db.execute(
                            select(EmailSyncState).where(
                                EmailSyncState.user_id == user.id
                            )
                        )
                    ).scalar_one_or_none()
                    if state is not None:
                        state.status = SyncStatusState.error.value
                        state.last_error = f"watch: {exc}"[:500]
                        state.last_sync_at = datetime.now(UTC)
            await db.commit()
    finally:
        await engine.dispose()
    return {"renewed": renewed, "failed": failed}
