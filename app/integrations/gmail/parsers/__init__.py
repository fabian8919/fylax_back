"""Parsers deterministas — Patrón Strategy / Factory (PRD §5.2, F2.4).

Cada remitente financiero frecuente tiene una REGLA de parseo en la
tabla ``parser_rules`` (semilla: ``parsers/seed.py``): dominios, regex
de monto/comercio/fecha y metadatos. Las reglas se editan en caliente
desde la BD — sin redespliegue cuando un banco cambia su plantilla
(PRD §13). El factory selecciona la regla según el dominio del
remitente; si no existe, se usa JEV como parser genérico. Los
remitentes con regla se procesan SIN llamada a JEV (costo cero —
PRD §F2.4).

Las reglas se cachean en memoria por ``_CACHE_TTL_SECONDS`` para no
golpear la BD por cada correo; ``invalidate_parser_cache()`` fuerza la
recarga (p. ej. tras editar una regla).

Los montos se asumen en formato COP ("." miles, "," decimales).
"""

import logging
import re
import time
from contextlib import suppress
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ParserRule
from app.integrations.gmail.jev_client import ExtractedTransaction
from app.integrations.gmail.parsers.seed import DEFAULT_PARSER_RULES

logger = logging.getLogger(__name__)

#: TTL del caché de reglas en segundos.
_CACHE_TTL_SECONDS = 300


class RuleParser:
    """Parser determinista construido desde una fila de parser_rules."""

    def __init__(
        self,
        *,
        name: str,
        domains: list[str],
        version: str,
        amount_pattern: str,
        merchant_pattern: str | None = None,
        merchant_static: str | None = None,
        date_pattern: str | None = None,
        date_format: str | None = None,
        currency: str = "COP",
        payment_method: str | None = None,
        suggested_category: str | None = None,
    ) -> None:
        self.name = name
        self.domains = tuple(domains)
        self.version = version
        self._amount_re = re.compile(amount_pattern)
        self._merchant_re = re.compile(merchant_pattern) if merchant_pattern else None
        self._merchant_static = merchant_static
        self._date_re = re.compile(date_pattern) if date_pattern else None
        self._date_format = date_format
        self._currency = currency
        self._payment_method = payment_method
        self._suggested_category = suggested_category

    @classmethod
    def from_rule(cls, rule: ParserRule) -> "RuleParser":
        """Construye el parser desde la fila ORM de parser_rules."""
        return cls(
            name=rule.name,
            domains=list(rule.domains),
            version=rule.version,
            amount_pattern=rule.amount_pattern,
            merchant_pattern=rule.merchant_pattern,
            merchant_static=rule.merchant_static,
            date_pattern=rule.date_pattern,
            date_format=rule.date_format,
            currency=rule.currency,
            payment_method=rule.payment_method,
            suggested_category=rule.suggested_category,
        )

    @classmethod
    def from_seed(cls, seed: dict) -> "RuleParser":
        """Construye el parser desde una entrada de DEFAULT_PARSER_RULES."""
        return cls(**{k: v for k, v in seed.items() if k != "id"})

    def parse(
        self, subject: str, body: str, default_date: date | None = None
    ) -> ExtractedTransaction | None:
        """Devuelve la transacción o None si la plantilla no coincide.

        default_date: fecha de recepción del correo; se usa cuando la
        regla no extrae fecha del cuerpo (sin date_pattern o sin match).
        """
        amount_match = self._amount_re.search(body)
        if not amount_match:
            return None  # plantilla cambió → cae a JEV (PRD §13)

        if self._merchant_re is not None:
            merchant_match = self._merchant_re.search(body)
            if not merchant_match:
                return None
            merchant = merchant_match.group(1).strip()
        else:
            merchant = self._merchant_static
        if not merchant:
            return None

        tx_date = default_date or date.today()
        if self._date_re is not None and self._date_format:
            date_match = self._date_re.search(body)
            if date_match:
                # Fecha inválida en el correo → se usa la de recepción.
                with suppress(ValueError):
                    tx_date = datetime.strptime(
                        date_match.group(1), self._date_format
                    ).date()

        # Formato COP: "." miles, "," decimales → "$129.900" = 129900.
        return ExtractedTransaction(
            merchant=merchant,
            amount=Decimal(amount_match.group(1).replace(".", "").replace(",", "")),
            date=tx_date,
            currency=self._currency,
            payment_method=self._payment_method,
            suggested_category=self._suggested_category,
        )


#: Caché en memoria: (timestamp monotonic, parsers). Los workers son
#: procesos long-lived; el TTL propaga los cambios de BD sin reinicio.
_parser_cache: tuple[float, list[RuleParser]] | None = None


async def load_parsers(db: AsyncSession) -> list[RuleParser]:
    """Carga las reglas habilitadas desde parser_rules (con caché TTL).

    Si la tabla está vacía (p. ej. migración pendiente) se usa la
    semilla en memoria para no degradar la ingesta.
    """
    global _parser_cache
    now = time.monotonic()
    if _parser_cache is not None and now - _parser_cache[0] < _CACHE_TTL_SECONDS:
        return _parser_cache[1]

    rows = (
        await db.execute(
            select(ParserRule)
            .where(ParserRule.enabled.is_(True))
            .order_by(ParserRule.name)
        )
    ).scalars().all()
    parsers = [RuleParser.from_rule(row) for row in rows]
    if not parsers:
        logger.warning("parser_rules vacío: usando semilla en memoria")
        parsers = [RuleParser.from_seed(seed) for seed in DEFAULT_PARSER_RULES]

    _parser_cache = (now, parsers)
    return parsers


def invalidate_parser_cache() -> None:
    """Fuerza la recarga de reglas en la próxima llamada a load_parsers."""
    global _parser_cache
    _parser_cache = None


def get_parser(sender_domain: str, parsers: list[RuleParser]) -> RuleParser | None:
    """Factory: elige el parser por dominio del remitente (PRD §5.2)."""
    domain = sender_domain.lower()
    for parser in parsers:
        if any(domain.endswith(d) for d in parser.domains):
            return parser
    return None  # remitente desconocido → JEV como parser genérico
