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
import logging

from celery import shared_task
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import EmailParseError
from app.integrations.gmail.parsers import get_parser
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

# Query de filtrado: solo correos que pueden contener movimientos
# financieros (PRD §F2.2). Se combina con el historyId incremental.
GMAIL_FINANCIAL_QUERY = (
    "from:(bancolombia.com.co OR alertasbancolombia.com.co OR amazon.com "
    "OR avianca.com OR nequi.com.co OR davivienda.com) "
    "subject:(compra OR compraste OR pagaste OR recibo OR factura OR pago) "
    "newer_than:30d"
)


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
        raise self.retry(exc=exc)


async def _process(email_address: str, history_id: str) -> int:
    """TODO(Fase 3) — pipeline completo de ingesta:
    1. Buscar el usuario por email y descifrar su google_refresh_token
       (TokenCipher — solo en memoria, nunca en logs).
    2. Gmail API users.history.list(historyId=último) → mensajes nuevos.
    3. users.messages.get para cada mensaje (format=full).
    4. Parser: get_parser(sender_domain) o JEV genérico.
    5. Insertar con source_ref_id = message.id → UNIQUE evita duplicados.
    6. Actualizar email_sync_state.gmail_history_id / last_sync_at.
    """
    raise NotImplementedError("Fase 3 — pipeline de ingesta Gmail")
