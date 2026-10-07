"""Parsers deterministas — Patrón Strategy / Factory (PRD §5.2, F2.4).

Cada remitente financiero frecuente tiene su parser (Bancolombia, Amazon,
Avianca…). Un factory selecciona el parser según el dominio del remitente;
si no existe, se usa JEV como parser genérico. Los remitentes con parser
propio se procesan SIN llamada a JEV (costo cero — PRD §F2.4).

Mitigación de riesgos (PRD §13): parsers versionados por remitente y
monitoreo de tasa de fallo por parser.
"""

import re
from abc import ABC, abstractmethod
from datetime import date
from decimal import Decimal

from app.integrations.gmail.jev_client import ExtractedTransaction


class TransactionParser(ABC):
    """Contrato de parser determinista por remitente."""

    #: Dominios del remitente que este parser sabe procesar.
    domains: tuple[str, ...] = ()

    #: Versión del parser: los bancos cambian plantillas (PRD §13).
    version: str = "v1"

    @abstractmethod
    def parse(self, subject: str, body: str) -> ExtractedTransaction | None:
        """Devuelve la transacción o None si la plantilla no coincide."""


class BancolombiaParser(TransactionParser):
    """Parser de alertas de compra de Bancolombia."""

    domains = ("bancolombia.com.co", "alertasbancolombia.com.co")
    version = "v1"

    _amount_re = re.compile(r"\$\s*([\d.,]+)")
    _merchant_re = re.compile(r"en\s+([A-Za-z0-9 &'.-]+?)(?:\s+el|\s*$)", re.IGNORECASE)

    def parse(self, subject: str, body: str) -> ExtractedTransaction | None:
        amount_match = self._amount_re.search(body)
        merchant_match = self._merchant_re.search(body)
        if not amount_match or not merchant_match:
            return None  # plantilla cambió → cae a JEV (PRD §13)

        return ExtractedTransaction(
            merchant=merchant_match.group(1).strip(),
            amount=Decimal(amount_match.group(1).replace(".", "").replace(",", "")),
            date=date.today(),  # TODO: extraer la fecha real del cuerpo
            currency="COP",
            payment_method="tarjeta_debito",
            suggested_category=None,
        )


class AmazonParser(TransactionParser):
    """Parser de confirmaciones de pedido de Amazon."""

    domains = ("amazon.com", "amazon.com.co")
    version = "v1"

    _total_re = re.compile(r"Total\s*[:]*\s*\$\s*([\d.,]+)")

    def parse(self, subject: str, body: str) -> ExtractedTransaction | None:
        match = self._total_re.search(body)
        if not match:
            return None
        return ExtractedTransaction(
            merchant="Amazon",
            amount=Decimal(match.group(1).replace(",", "")),
            date=date.today(),
            currency="COP",
            payment_method=None,
            suggested_category="Compras",
        )


class AviancaParser(TransactionParser):
    """Parser de confirmaciones de compra de tiquetes Avianca."""

    domains = ("avianca.com", "avianca.com.co")
    version = "v1"

    def parse(self, subject: str, body: str) -> ExtractedTransaction | None:
        # TODO(Fase 3): reglas del layout real de Avianca.
        return None


#: Registro de parsers: crecer aquí suma remitentes sin tocar el pipeline.
PARSERS: list[TransactionParser] = [
    BancolombiaParser(),
    AmazonParser(),
    AviancaParser(),
]


def get_parser(sender_domain: str) -> TransactionParser | None:
    """Factory: elige el parser por dominio del remitente (PRD §5.2)."""
    domain = sender_domain.lower()
    for parser in PARSERS:
        if any(domain.endswith(d) for d in parser.domains):
            return parser
    return None  # remitente desconocido → JEV como parser genérico
