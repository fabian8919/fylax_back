"""Semilla de reglas de parseo por remitente (tabla parser_rules).

Los UUIDs son fijos para que la migración y los entornos compartan los
mismos ids. La migración 0004 importa esta lista: mantenerla como
ÚNICA fuente de verdad de las reglas iniciales.

Convenciones de los patrones:
- amount_pattern: regex con el monto en el grupo 1, formato COP
  ("." miles, "," decimales).
- merchant_pattern: regex con el comercio en el grupo 1; si es None se
  usa merchant_static.
- date_pattern: regex con la fecha COMPLETA en el grupo 1, parseada
  con date_format (strptime).
- Los flags de regex se escriben inline (p. ej. ``(?i)`` al inicio).
"""

#: Cada entrada es una fila de parser_rules (ver app.db.models.ParserRule).
DEFAULT_PARSER_RULES: list[dict] = [
    {
        "id": "00000000-0000-4000-8000-000000000101",
        "name": "bancolombia",
        # TEMPORAL — "gmail.com" solo para pruebas con reenvío desde
        # Gmail. QUITAR de la fila en BD antes de producción.
        "domains": ["bancolombia.com.co", "alertasbancolombia.com.co", "gmail.com"],
        "version": "v1",
        "amount_pattern": r"\$\s*([\d.,]+)",
        "merchant_pattern": r"(?i)en\s+([A-Za-z0-9 &'.-]+?)(?:\s+el|\s*$)",
        "merchant_static": None,
        "date_pattern": None,  # TODO: extraer la fecha real del cuerpo
        "date_format": None,
        "currency": "COP",
        "payment_method": "tarjeta_debito",
        "suggested_category": None,
    },
    {
        "id": "00000000-0000-4000-8000-000000000102",
        "name": "amazon",
        "domains": ["amazon.com", "amazon.com.co"],
        "version": "v1",
        "amount_pattern": r"Total\s*[:]*\s*\$\s*([\d.,]+)",
        "merchant_pattern": None,
        "merchant_static": "Amazon",
        "date_pattern": None,
        "date_format": None,
        "currency": "COP",
        "payment_method": None,
        "suggested_category": "Compras",
    },
    {
        "id": "00000000-0000-4000-8000-000000000103",
        "name": "bbva",
        "domains": ["bbva.com.co", "bbva.com"],
        "version": "v1",
        "amount_pattern": r"\$\s*([\d.,]+)",
        "merchant_pattern": r"(?i)en\s+([A-Za-z0-9 &'.-]+?)(?:\s+el\s|\s+con\s|\.\s|\s*$)",
        "merchant_static": None,
        "date_pattern": r"(\d{2}/\d{2}/\d{4})",
        "date_format": "%d/%m/%Y",
        "currency": "COP",
        "payment_method": None,
        "suggested_category": None,
    },
]
