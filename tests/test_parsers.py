"""Tests de precisión de los parsers deterministas (PRD §F2.4, Fase 6).

Los parsers son reglas dinámicas (tabla parser_rules); estos tests
validan los patrones de la SEMILLA (parsers/seed.py) contra cuerpos de
correo reales anonimizados de cada plantilla (BBVA compra/retiro/
transferencias/PSE/facturas/Bre-B), el filtro por asunto y la
normalización de montos (parse_amount).

Criterio de aceptación F2.3: precisión ≥ 90% en monto y comercio sobre un
set de prueba de al menos 30 correos reales anonimizados.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.integrations.gmail.parsers import RuleParser, get_parsers, parse_amount
from app.integrations.gmail.parsers.seed import DEFAULT_PARSER_RULES

PARSERS: dict[str, RuleParser] = {
    seed["name"]: RuleParser.from_seed(seed) for seed in DEFAULT_PARSER_RULES
}


def _pipeline(domain: str, subject: str, body: str, default_date=None):
    """Réplica del bucle del worker: reglas del dominio por prioridad,
    filtradas por asunto, hasta que una parsee."""
    for parser in get_parsers(domain, list(PARSERS.values())):
        if not parser.matches_subject(subject):
            continue
        parsed = parser.parse(subject, body, default_date=default_date)
        if parsed is not None:
            return parsed
    return None


class TestParseAmount:
    """Formatos mixtos CO/US/Bre-B (bug: '$48,270.00' quedaba 4827000)."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("48,270.00", Decimal("48270.00")),  # coma miles, punto decimal
            ("500,000.00", Decimal("500000.00")),
            ("2,500,000.00", Decimal("2500000.00")),
            ("38.000,00", Decimal("38000.00")),  # Bre-B: punto miles, coma decimal
            ("129.900", Decimal("129900")),  # COP: punto miles sin decimales
            ("48.270", Decimal("48270")),
            ("500,000", Decimal("500000")),  # coma miles sin decimales
            ("38,00", Decimal("38.00")),  # coma decimal
            ("843,000.00", Decimal("843000.00")),
            ("1.234.567", Decimal("1234567")),  # varios puntos de miles
        ],
    )
    def test_formatos(self, raw, expected):
        assert parse_amount(raw) == expected


class TestParserFactory:
    def test_dominio_conocido_devuelve_sus_reglas_ordenadas(self):
        parsers = list(PARSERS.values())
        assert [p.name for p in get_parsers("alertasbancolombia.com.co", parsers)] == [
            "bancolombia"
        ]
        bbva = get_parsers("bbvanet.com.co", parsers)
        assert [p.name for p in bbva] == [
            "bbva_compra",
            "bbva_retiro",
            "bbva_transferencia",
            "bbva_transferencia_camino",
            "bbva_pse",
            "bbva_facturas",
        ]
        assert [p.name for p in get_parsers("bbva.com", parsers)] == ["bbva_breb"]

    def test_dominio_desconocido_devuelve_lista_vacia(self):
        assert get_parsers("tienda-desconocida.com", list(PARSERS.values())) == []


class TestSubjectFilter:
    def test_regla_solo_aplica_si_el_asunto_coincide(self):
        compra = PARSERS["bbva_compra"]
        assert compra.matches_subject("Compra Exitosa")
        assert not compra.matches_subject("¡Gana hasta $950.000 con tu Débito BBVA!")

    def test_marketing_no_parsea_como_transaccion(self):
        # El correo de marketing de BBVA no cumple el subject_pattern de
        # ninguna regla → el pipeline devuelve None (falso positivo).
        body = "Gana hasta $950.000! Inscríbete y compra con tu Débito BBVA"
        assert _pipeline("bbvanet.com.co", "¡Gana hasta $950.000!", body) is None


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

    def test_sin_date_pattern_usa_fecha_de_recepcion(self):
        body = (
            "Bancolombia te informa: compraste por $45.500 "
            "en TIENDA EJEMPLO S.A. el 05/10/2026 con tu tarjeta débito."
        )
        tx = self.PARSER.parse(subject="", body=body, default_date=date(2026, 11, 20))
        assert tx is not None
        assert tx.date.isoformat() == "2026-11-20"

    def test_plantilla_cambiada_devuelve_none(self):
        assert self.PARSER.parse(subject="", body="Texto sin estructura") is None


class TestAmazonParser:
    PARSER = PARSERS["amazon"]

    def test_pedido_con_total(self):
        body = "Tu pedido fue confirmado.\nTotal: $129.900\nGracias por comprar."
        tx = self.PARSER.parse(subject="", body=body)
        assert tx is not None
        assert tx.merchant == "Amazon"
        assert tx.amount == 129_900


class TestBBVACompra:
    def test_compra_exitosa(self):
        body = (
            "Detalles de la operación: Tarjeta terminada en: *2269 "
            "Fecha de la operación: 2026-11-24 Establecimiento: Easy gaitan corte "
            "Valor: $48,270.00"
        )
        tx = _pipeline("bbvanet.com.co", "Compra Exitosa", body)
        assert tx is not None
        assert tx.merchant == "Easy gaitan corte"
        assert tx.amount == Decimal("48270.00")
        assert tx.date.isoformat() == "2026-11-24"


class TestBBVARetiro:
    def test_retiro_sin_tarjeta(self):
        body = (
            "Te informamos que el día 2026-11-12 a las 13:11, realizaste un "
            "retiro sin tarjeta de la cuenta terminada en 64 por un valor de "
            "$500,000.00, a través de nuestro servicio de Cajeros Automáticos."
        )
        tx = _pipeline(
            "bbvanet.com.co", "BBVA Retiro en Cajero Automatico sin Tarjeta", body
        )
        assert tx is not None
        assert tx.merchant == "Retiro cajero automático"
        assert tx.amount == Decimal("500000.00")
        assert tx.date.isoformat() == "2026-11-12"


class TestBBVATransferencias:
    def test_notificacion_transferencia(self):
        body = (
            "Tipo de transacción: Transferencia de BBVA a BBVA "
            "Cuenta terminada en: *1964 Cuenta destino terminada en: *9425 "
            "Fecha de la operación: 2026-11-19 Valor: $2,500,000.00 Hora: 21:21"
        )
        tx = _pipeline(
            "bbvanet.com.co", "BBVA Móvil - Notificación de Transferencias", body
        )
        assert tx is not None
        assert tx.merchant == "*9425"
        assert tx.amount == Decimal("2500000.00")
        assert tx.date.isoformat() == "2026-11-19"

    def test_transferencia_en_camino(self):
        body = (
            "Debitamos los $ 843,000.00 de tu cuenta y los enviamos a "
            "Adriana Chary. Conoce cuándo la recibirá."
        )
        tx = _pipeline(
            "bbvanet.com.co",
            "Tu transferencia va en camino",
            body,
            default_date=date(2026, 11, 25),
        )
        assert tx is not None
        assert tx.merchant == "Adriana Chary"
        assert tx.amount == Decimal("843000.00")
        assert tx.date.isoformat() == "2026-11-25"  # sin fecha en cuerpo → recepción


class TestBBVAPse:
    def test_pago_pse(self):
        body = (
            "Tipo de transacción: Pago PSE Cuenta terminada en: *1964 "
            "Fecha de la operación: 2026-11-13 Establecimiento: 101 FINTECH S.A "
            "Valor: $18,720.00"
        )
        tx = _pipeline("bbvanet.com.co", "BBVA Net - Pagos PSE", body)
        assert tx is not None
        assert tx.merchant == "101 FINTECH S.A"
        assert tx.amount == Decimal("18720.00")
        assert tx.date.isoformat() == "2026-11-13"


class TestBBVAFacturas:
    def test_pago_de_facturas(self):
        body = (
            "Realizaste un pago por $30,990.00 de 5706 HOGAR Y MOVIL MOVISTAR W, "
            "referencia de pago 60202071741 desde tu cuenta No.XXXX4238. "
            "Hora 09:44 el 2026-11-20. Comprobante 000004646"
        )
        tx = _pipeline("bbvanet.com.co", "BBVA Móvil - Pago de Facturas", body)
        assert tx is not None
        assert tx.merchant == "HOGAR Y MOVIL MOVISTAR W"
        assert tx.amount == Decimal("30990.00")
        assert tx.date.isoformat() == "2026-11-20"
        assert tx.suggested_category == "Servicios"


class TestBBVABreB:
    def test_envio_breb(self):
        body = (
            "Marco fabian Zabala , tu envío a través de Bre-B fue exitoso. "
            "La llave *****5553 recibió el valor que enviaste. "
            "Detalles de la operación Fecha y hora 2026/11/23 17:17 "
            "Valor enviado $ 38.000,00 "
            "Persona que recibe PAPELERIA LA NUEVA NORMA "
            "Entidad que recibe Bold Tipo de llave Código de comercio"
        )
        tx = _pipeline("bbva.com", "El envío se completó correctamente", body)
        assert tx is not None
        # El comercio es el destinatario real, no la llave enmascarada.
        assert tx.merchant == "PAPELERIA LA NUEVA NORMA"
        assert tx.amount == Decimal("38000.00")
        assert tx.date.isoformat() == "2026-11-23"


@pytest.mark.skip(reason="Fase 6: cargar set de 30+ correos anonimizados")
def test_precision_global_mayor_90_por_ciento():
    ...
