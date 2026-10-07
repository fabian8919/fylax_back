"""Tarea de ingesta: process_new_email (PRD §5.3 — flujo operativo pasos 3-6).

1. El webhook encoló esta tarea con el historyId del correo nuevo.
2. El worker descarga SOLO los correos nuevos desde el último historyId
   con queries específicas (dominios bancarios, asuntos de recibo —
   PRD §F2.2). Correos personales o promocionales sin datos de pago
   nunca generan transacciones.
3. Parser determinista (Strategy) o JEV como genérico (F2.3/F2.4).
4. Se valida con Pydantic y se inserta; UNIQUE (user_id, source_ref_id)
   garantiza idempotencia (F2.6).
5. Los cuerpos de correo se procesan EN MEMORIA y NO se persisten
   (PRD §10 — privacidad); solo se guarda la transacción estructurada.
"""

import asyncio
import base64
import logging
import re
from datetime import UTC, datetime

from googleapiclient.errors import HttpError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.categories.seed import FALLBACK_CATEGORY_NAME
from app.core.config import get_settings
from app.core.security import TokenCipher
from app.db.models import (
    Category,
    EmailSyncState,
    SyncStatusState,
    Transaction,
    TransactionSource,
    User,
)
from app.integrations.gmail.client import build_gmail_service
from app.integrations.gmail.jev_client import ExtractedTransaction, JevClient
from app.integrations.gmail.parsers import get_parser
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

# Query de filtrado: solo correos que pueden contener movimientos
# financieros (PRD §F2.2). Se usa como fallback cuando el historyId
# incremental ya no es válido (404 → se re-sincroniza lo reciente).
GMAIL_FINANCIAL_QUERY = (
    "from:(bancolombia.com.co OR alertasbancolombia.com.co OR amazon.com "
    "OR avianca.com OR nequi.com.co OR davivienda.com) "
    "subject:(compra OR compraste OR pagaste OR recibo OR factura OR pago) "
    "newer_than:30d"
)

_TAG_RE = re.compile(r"<[^>]+>")


@celery_app.task(
    bind=True,
    max_retries=3,
    retry_backoff=True,  # backoff exponencial (F2.5)
    retry_jitter=True,
)
def process_new_email(
    self,
    email_address: str,
    history_id: str,
) -> dict:
    """Procesa los correos nuevos de un usuario. Idempotente por diseño."""
    try:
        inserted = asyncio.run(_process(email_address, history_id))
        return {"processed": True, "inserted": inserted}
    except Exception as exc:
        # Reintento 1→2→3 y luego dead-letter registrado (F2.5).
        logger.exception("process_new_email falló: %s", exc)
        raise self.retry(exc=exc) from exc


async def _process(email_address: str, history_id: str) -> int:
    """Pipeline completo de ingesta (ver docstring del módulo)."""
    settings = get_settings()

    # Engine propio con NullPool: cada tarea Celery corre asyncio.run()
    # (loop nuevo) y el engine global de app.db.session quedaría atado
    # a otro loop. NullPool evita reusar conexiones entre loops.
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    try:
        async with session_factory() as db:
            return await _run_pipeline(db, settings, email_address, history_id)
    finally:
        await engine.dispose()


async def _run_pipeline(
    db: AsyncSession, settings, email_address: str, history_id: str
) -> int:
    # 1. Usuario + refresh token descifrado SOLO en memoria (F1.3).
    user = (
        await db.execute(select(User).where(User.email == email_address))
    ).scalar_one_or_none()
    if user is None or not user.google_refresh_token:
        logger.warning("Ingesta ignorada: usuario %s sin registro/token", email_address)
        return 0

    cipher = TokenCipher(settings.token_encryption_key)
    refresh_token = cipher.decrypt(user.google_refresh_token)

    state = (
        await db.execute(
            select(EmailSyncState).where(EmailSyncState.user_id == user.id)
        )
    ).scalar_one_or_none()
    if state is None:
        state = EmailSyncState(user_id=user.id)
        db.add(state)

    try:
        service = build_gmail_service(refresh_token)
        message_ids = _list_new_message_ids(
            service, state.gmail_history_id or history_id
        )

        inserted = 0
        jev = JevClient()
        for message_id in message_ids:
            if await _process_message(db, service, jev, user.id, message_id):
                inserted += 1

        # 6. Estado de sincronización: avance exitoso.
        state.gmail_history_id = history_id or state.gmail_history_id
        state.last_sync_at = datetime.now(UTC)
        state.status = SyncStatusState.active.value
        state.last_error = None
        await db.commit()
        return inserted
    except Exception as exc:
        # 5b. El error queda visible en GET /sync/status (F3.4) y la
        # tarea se reintenta con backoff (F2.5).
        await db.rollback()
        fresh = (
            await db.execute(
                select(EmailSyncState).where(EmailSyncState.user_id == user.id)
            )
        ).scalar_one_or_none()
        if fresh is None:
            fresh = EmailSyncState(user_id=user.id)
            db.add(fresh)
        fresh.status = SyncStatusState.error.value
        fresh.last_error = str(exc)[:500]
        await db.commit()
        raise


def _list_new_message_ids(service, start_history_id: str | None) -> list[str]:
    """Mensajes nuevos vía users.history.list; fallback a búsqueda (F2.2)."""
    if start_history_id:
        try:
            ids: list[str] = []
            page_token = None
            while True:
                resp = (
                    service.users()
                    .history()
                    .list(
                        userId="me",
                        startHistoryId=start_history_id,
                        historyTypes=["messageAdded"],
                        pageToken=page_token,
                    )
                    .execute()
                )
                for record in resp.get("history", []):
                    ids.extend(m["id"] for m in record.get("messages", []))
                page_token = resp.get("nextPageToken")
                if not page_token:
                    break
            if ids:
                return list(dict.fromkeys(ids))  # dedup conservando orden
        except HttpError as exc:
            if exc.status_code != 404:
                raise
            # historyId expirado (>7 días sin sync): re-sincronización.
            logger.info("historyId expirado; fallback a búsqueda financiera")

    resp = (
        service.users()
        .messages()
        .list(userId="me", q=GMAIL_FINANCIAL_QUERY, maxResults=10)
        .execute()
    )
    return [m["id"] for m in resp.get("messages", [])]


async def _process_message(
    db: AsyncSession, service, jev: JevClient, user_id, message_id: str
) -> bool:
    """Descarga, parsea e inserta UN mensaje. True si generó transacción."""
    msg = (
        service.users()
        .messages()
        .get(userId="me", id=message_id, format="full")
        .execute()
    )
    headers = {h["name"].lower(): h["value"] for h in msg["payload"]["headers"]}
    sender = headers.get("from", "")
    subject = headers.get("subject", "")
    body = _extract_body(msg["payload"])

    # 3. Parser determinista por dominio; JEV como genérico (F2.3/F2.4).
    domain = sender.split("@")[-1].rstrip(">").strip()
    parsed: ExtractedTransaction | None = None
    parser = get_parser(domain)
    if parser is not None:
        parsed = parser.parse(subject, body)
    if parsed is None and body.strip():
        parsed = await jev.extract(body[:8000])
    if parsed is None or not parsed.merchant or parsed.amount <= 0:
        return False  # no era un movimiento financiero

    # 4. Categoría sugerida por JEV → catálogo; fallback "Otros".
    category_id = await _resolve_category_id(db, parsed.suggested_category)

    tx = Transaction(
        user_id=user_id,
        category_id=category_id,
        amount=parsed.amount,
        currency=parsed.currency or "COP",
        date=datetime.combine(parsed.date, datetime.min.time()),
        merchant_clean=parsed.merchant.strip(),
        source=TransactionSource.gmail_api.value,
        source_ref_id=message_id,
    )
    db.add(tx)
    try:
        # Savepoint: un duplicado (mismo source_ref_id) revierte SOLO
        # este insert y el resto del lote continúa (F2.6).
        async with db.begin_nested():
            await db.flush()
        return True
    except IntegrityError:
        logger.info("Duplicado ignorado (idempotente): %s", message_id)
        return False


async def _resolve_category_id(db: AsyncSession, suggested: str | None):
    if suggested:
        result = await db.execute(
            select(Category.id).where(Category.name.ilike(suggested.strip()))
        )
        found = result.scalar_one_or_none()
        if found is not None:
            return found
    fallback = await db.execute(
        select(Category.id).where(
            Category.name == FALLBACK_CATEGORY_NAME, Category.user_id.is_(None)
        )
    )
    return fallback.scalar_one()


def _extract_body(payload: dict) -> str:
    """Texto plano del correo; decodifica base64url y limpia HTML básico.

    El cuerpo vive solo en memoria durante el parseo (PRD §10).
    """
    mime = payload.get("mimeType", "")
    data = (payload.get("body") or {}).get("data")

    if not data:
        for part in payload.get("parts", []):
            text = _extract_body(part)
            if text:
                return text
        return ""

    decoded = base64.urlsafe_b64decode(data + "==").decode("utf-8", "replace")
    if mime == "text/html":
        decoded = _TAG_RE.sub(" ", decoded)
    return re.sub(r"\s+", " ", decoded).strip()
