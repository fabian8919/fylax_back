"""Cliente del motor de IA JEV (PRD §4, F2.3).

El cuerpo del correo (HTML/texto plano) se envía con un system prompt
estricto que EXIGE salida JSON:
{merchant, amount, date, currency, payment_method, suggested_category}

El resultado se valida contra el schema Pydantic antes de tocar la base
de datos (PRD §5.2). Mitigación de costos (PRD §13): JEV solo se invoca
para remitentes sin parser propio o correos que el parser determinista
no logró resolver.
"""

import logging
from datetime import date
from decimal import Decimal

import httpx
from pydantic import BaseModel, Field

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class ExtractedTransaction(BaseModel):
    """Schema de salida de JEV — validado antes de persistir (PRD §F2.3)."""

    merchant: str = Field(min_length=1, max_length=255)
    amount: Decimal
    date: date
    currency: str = Field(min_length=3, max_length=3)
    payment_method: str | None = None
    suggested_category: str | None = None


SYSTEM_PROMPT = """Eres el extractor de transacciones financieras de Fylax.
Analiza el cuerpo del correo (alerta bancaria o recibo de comercio) y
devuelve ÚNICAMENTE un JSON válido con estas claves exactas:
{"merchant": string, "amount": number, "date": "YYYY-MM-DD",
 "currency": "COP", "payment_method": string|null,
 "suggested_category": string|null}
Reglas:
- amount es el valor absoluto del dinero movido (sin signo).
- merchant es el nombre comercial limpio del comercio/beneficiario.
- Si el correo NO contiene una transacción financiera, responde:
  {"merchant": "", "amount": 0, "date": null, "currency": "COP",
   "payment_method": null, "suggested_category": null}
No agregues texto ni markdown fuera del JSON."""


class JevClient:
    def __init__(self) -> None:
        settings = get_settings()
        # JEV es opcional en dev: sin credenciales los correos sin parser
        # determinista se ignoran en vez de romper la tarea entera.
        self._enabled = bool(settings.jev_api_key and settings.jev_base_url)
        self._http = (
            httpx.AsyncClient(
                base_url=settings.jev_base_url,
                headers={"Authorization": f"Bearer {settings.jev_api_key}"},
                timeout=httpx.Timeout(30.0),
            )
            if self._enabled
            else None
        )

    async def extract(self, email_body: str) -> ExtractedTransaction | None:
        """Extrae la transacción; None si el correo no es financiero."""
        if not self._enabled or self._http is None:
            logger.warning("JEV no configurado: correo sin parser ignorado")
            return None
        response = await self._http.post(
            "/extract",
            json={"system": SYSTEM_PROMPT, "input": email_body},
        )
        response.raise_for_status()
        return ExtractedTransaction.model_validate(response.json())
