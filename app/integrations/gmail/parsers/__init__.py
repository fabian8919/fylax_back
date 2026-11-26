"""Parsers deterministas — Patrón Strategy / Factory (PRD §5.2, F2.4).

Cada remitente financiero frecuente tiene una o varias REGLAS de parseo
en la tabla ``parser_rules`` (semilla: ``parsers/seed.py``): dominios,
regex de monto/comercio/fecha y metadatos. Las reglas se editan en
caliente desde la BD — sin redespliegue cuando un banco cambia su
plantilla (PRD §13).

Un dominio puede tener VARIAS reglas (una por tipo de movimiento:
compra, retiro, transferencia, pago PSE/facturas…). El factory devuelve
todas las del dominio ordenadas por ``priority``; la regla solo se
intenta si el asunto cumple su ``subject_pattern`` — así los correos de
marketing del mismo banco nunca llegan al regex de montos. Si ninguna
regla aplica, se usa JEV como parser genérico (PRD §F2.4).

Las reglas se cachean en memoria por ``_CACHE_TTL_SECONDS`` para no
golpear la BD por cada correo; ``invalidate_parser_cache()`` fuerza la
recarga (p. ej. tras editar una regla).

Los montos se normalizan con ``parse_amount`` (formatos CO/US mixtos).
"""

import logging
import re
import time
from contextlib import suppress
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ParserRule
from app.integrations.gmail.jev_client import ExtractedTransaction
from app.integrations.gmail.parsers.seed import DEFAULT_PARSER_RULES

logger = logging.getLogger(__name__)

#: TTL del caché de reglas en segundos.
_CACHE_TTL_SECONDS = 300


def parse_amount(raw: str) -> Decimal:
    """Normaliza un monto con separadores de miles/decimales mixtos.

    Los bancos colombianos usan formatos inconsistentes entre plantillas:
    - "48,270.00"  (coma miles, punto decimal — estilo US)
    - "38.000,00"  (punto miles, coma decimal — Bre-B)
    - "129.900"    (punto miles, sin decimales — COP clásico)
    - "2,500,000.00" / "500,000.00"

    Regla: el separador MÁS A LA DERECHA es el decimal; con un solo
    separador seguido de 3 dígitos se asume separador de miles.
    """
    s = raw.strip().rstrip(".,")  # el regex puede capturar un separador final
    has_dot, has_comma = "." in s, "," in s
    if has_dot and has_comma:
        if s.rfind(".") > s.rfind(","):
            s = s.replace(",", "")  # 48,270.00 → 48270.00
        else:
            s = s.replace(".", "").replace(",", ".")  # 38.000,00 → 38000.00
    elif has_dot and s.count(".") == 1 and len(s.rsplit(".", 1)[1]) == 3:
        s = s.replace(".", "")  # 129.900 → 129900 (miles)
    elif has_comma and s.count(",") == 1 and len(s.rsplit(",", 1)[1]) == 3:
        s = s.replace(",", "")  # 48,270 → 48270 (miles)
    elif has_dot and s.count(".") > 1:
        s = s.replace(".", "")  # 1.234.567 → 1234567
    elif has_comma and s.count(",") > 1:
        s = s.replace(",", "")  # 2,500,000 → 2500000
    else:
        s = s.replace(",", ".")  # 38,00 → 38.00 (decimal)
    return Decimal(s)


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
        subject_pattern: str | None = None,
        priority: int = 100,
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
        self._subject_re = re.compile(subject_pattern) if subject_pattern else None
        self.priority = priority
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
            subject_pattern=rule.subject_pattern,
            priority=rule.priority,
            currency=rule.currency,
            payment_method=rule.payment_method,
            suggested_category=rule.suggested_category,
        )

    @classmethod
    def from_seed(cls, seed: dict) -> "RuleParser":
        """Construye el parser desde una entrada de DEFAULT_PARSER_RULES."""
        return cls(**{k: v for k, v in seed.items() if k != "id"})

    def matches_subject(self, subject: str) -> bool:
        """True si la regla aplica al asunto (sin patrón = siempre).

        Es el filtro por tipo de movimiento: los correos de marketing
        del banco no cumplen el subject_pattern de ninguna regla y
        jamás llegan al regex de montos (falsos positivos, PRD §13).
        """
        return self._subject_re is None or bool(self._subject_re.search(subject))

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
        try:
            amount = parse_amount(amount_match.group(1))
        except InvalidOperation:
            return None

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

        return ExtractedTransaction(
            merchant=merchant,
            amount=amount,
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
            .order_by(ParserRule.priority, ParserRule.name)
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


def get_parsers(sender_domain: str, parsers: list[RuleParser]) -> list[RuleParser]:
    """Factory: reglas del dominio del remitente, por priority (PRD §5.2).

    Un dominio puede tener varias reglas (una por tipo de movimiento);
    el pipeline las intenta en orden hasta que una parsee. Lista vacía
    = remitente desconocido → JEV como parser genérico.
    """
    domain = sender_domain.lower()
    matched = [p for p in parsers if any(domain.endswith(d) for d in p.domains)]
    return sorted(matched, key=lambda p: p.priority)
