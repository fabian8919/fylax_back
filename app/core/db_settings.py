"""Configuración dinámica en BD (tabla app_settings, 0005).

Par clave/valor para parámetros operativos editables en caliente sin
redespliegue — p. ej. ``gmail_financial_query``, la búsqueda de Gmail
del fallback cuando el historyId incremental expira (PRD §F2.2).

Los valores se cachean en memoria por ``_CACHE_TTL_SECONDS`` para no
golpear la BD por cada tarea; ``invalidate_settings_cache()`` fuerza la
recarga tras editar una fila.
"""

import logging
import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AppSetting

logger = logging.getLogger(__name__)

#: TTL del caché de configuración en segundos.
_CACHE_TTL_SECONDS = 300

#: Valores iniciales: la migración 0005 siembra la tabla desde aquí y
#: el código los usa como fallback si la fila no existe en la BD.
DEFAULT_SETTINGS: dict[str, str] = {
    # Búsqueda de respaldo de Gmail: solo correos que pueden contener
    # movimientos financieros (PRD §F2.2). Se usa cuando el historyId
    # incremental ya no es válido (404 → se re-sincroniza lo reciente).
    "gmail_financial_query": (
        "from:(bancolombia.com.co OR alertasbancolombia.com.co OR amazon.com "
        "OR avianca.com OR nequi.com.co OR davivienda.com OR bbva.com.co "
        "OR bbva.com) "
        "subject:(compra OR compraste OR pagaste OR recibo OR factura OR pago) "
        "newer_than:30d"
    ),
}

#: Caché en memoria: clave → (timestamp monotonic, valor).
_cache: dict[str, tuple[float, str]] = {}


async def get_setting(db: AsyncSession, key: str) -> str | None:
    """Valor de la clave desde app_settings; fallback a DEFAULT_SETTINGS."""
    now = time.monotonic()
    cached = _cache.get(key)
    if cached is not None and now - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1]

    value = (
        await db.execute(select(AppSetting.value).where(AppSetting.key == key))
    ).scalar_one_or_none()
    if value is None:
        value = DEFAULT_SETTINGS.get(key)
        if value is None:
            logger.warning("app_settings: clave desconocida '%s'", key)
            return None
        logger.warning("app_settings: '%s' no está en BD, usando default", key)

    _cache[key] = (now, value)
    return value


def invalidate_settings_cache() -> None:
    """Fuerza la recarga de configuración en la próxima llamada."""
    _cache.clear()
