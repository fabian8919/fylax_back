"""Tests de precisión de los parsers deterministas (PRD §F2.4, Fase 6).

Criterio de aceptación F2.3: precisión ≥ 90% en monto y comercio sobre un
set de prueba de al menos 30 correos reales anonimizados. Los fixtures de
correos anonimizados se agregan en la Fase 6 (no commitear PII).
"""

import pytest

from app.integrations.gmail.parsers import (
    AmazonParser,
    BancolombiaParser,
    get_parser,
)


class TestParserFactory:
    def test_domino_conocido_devuelve_parser_propio(self):
        assert isinstance(get_parser("alertas@alertasbancolombia.com.co"), BancolombiaParser)
        assert isinstance(get_parser("auto-confirm@amazon.com"), AmazonParser)

    def test_domino_desconocido_devuelve_none_usa_jev(self):
        # Remitente desconocido → None → el pipeline cae a JEV genérico.
        assert get_parser("promo@tienda-desconocida.com") is None


class TestBancolombiaParser:
    PARSER = BancolombiaParser()

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
    PARSER = AmazonParser()

    def test_pedido_con_total(self):
        body = "Tu pedido fue confirmado.\nTotal: $129.900\nGracias por comprar."
        tx = self.PARSER.parse(subject="", body=body)
        assert tx is not None
        assert tx.merchant == "Amazon"
        assert tx.amount == 129_900


@pytest.mark.skip(reason="Fase 6: cargar set de 30+ correos anonimizados")
def test_precision_global_mayor_90_por_ciento():
    ...
