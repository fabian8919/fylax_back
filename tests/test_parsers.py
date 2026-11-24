"""Tests de precisión de los parsers deterministas (PRD §F2.4, Fase 6).

Los parsers ahora son reglas dinámicas (tabla parser_rules); estos
tests validan los patrones de la SEMILLA (parsers/seed.py), que es lo
que la migración 0004 inserta en la BD.

Criterio de aceptación F2.3: precisión ≥ 90% en monto y comercio sobre un
set de prueba de al menos 30 correos reales anonimizados. Los fixtures de
correos anonimizados se agregan en la Fase 6 (no commitear PII).
"""

import pytest

from app.integrations.gmail.parsers import RuleParser, get_parser
from app.integrations.gmail.parsers.seed import DEFAULT_PARSER_RULES

PARSERS: dict[str, RuleParser] = {
    seed["name"]: RuleParser.from_seed(seed) for seed in DEFAULT_PARSER_RULES
}


class TestParserFactory:
    def test_domino_conocido_devuelve_parser_propio(self):
        parsers = list(PARSERS.values())
        assert get_parser("alertas@alertasbancolombia.com.co", parsers) is PARSERS[
            "bancolombia"
        ]
        assert get_parser("auto-confirm@amazon.com", parsers) is PARSERS["amazon"]
        assert get_parser("notificaciones@bbva.com.co", parsers) is PARSERS["bbva"]

    def test_domino_desconocido_devuelve_none_usa_jev(self):
        # Remitente desconocido → None → el pipeline cae a JEV genérico.
        assert get_parser("promo@tienda-desconocida.com", list(PARSERS.values())) is None


class TestBancolombiaParser:
    PARSER = PARSERS["bancolombia"]

    def test_compra_simple(self):
        body = (
            "Bancolombia te informa: compraste por $45.500 "
            "en TIENDA EJEMPLO S.A. el 05/10/2026 con tu tarjeta débito."
        )
        tx = self.PARSER.parse(subject="", body=body)
        assert tx is not None
        assert tx.merchant == "TIENDA EJEMPLO S.A."
        assert tx.amount == 45_500
        assert tx.currency == "COP"

    def test_plantilla_cambiada_devuelve_none(self):
        # Si el banco cambia la plantilla, el parser no inventa datos:
        # devuelve None y el pipeline usa JEV (mitigación PRD §13).
        assert self.PARSER.parse(subject="", body="Texto sin estructura") is None


class TestAmazonParser:
    PARSER = PARSERS["amazon"]

    def test_pedido_con_total(self):
        body = "Tu pedido fue confirmado.\nTotal: $129.900\nGracias por comprar."
        tx = self.PARSER.parse(subject="", body=body)
        assert tx is not None
        assert tx.merchant == "Amazon"
        assert tx.amount == 129_900


class TestBBVAParser:
    PARSER = PARSERS["bbva"]

    def test_compra_simple(self):
        body = (
            "BBVA te informa: compra por $120.000 en ALMACEN EJEMPLO "
            "el 17/11/2026."
        )
        tx = self.PARSER.parse(subject="", body=body)
        assert tx is not None
        assert tx.merchant == "ALMACEN EJEMPLO"
        assert tx.amount == 120_000
        assert tx.currency == "COP"
        assert tx.date.isoformat() == "2026-11-17"

    def test_plantilla_cambiada_devuelve_none(self):
        assert self.PARSER.parse(subject="", body="Texto sin estructura") is None


@pytest.mark.skip(reason="Fase 6: cargar set de 30+ correos anonimizados")
def test_precision_global_mayor_90_por_ciento():
    ...
