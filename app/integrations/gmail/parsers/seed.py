"""Semilla de reglas de parseo por remitente (tabla parser_rules).

Los UUIDs son fijos para que la migración y los entornos compartan los
mismos ids. La migración 0004 siembra bancolombia/amazon y la 0006
reemplaza la regla única de BBVA por la familia por tipo de movimiento.
Mantenerla como ÚNICA fuente de verdad de las reglas iniciales.

Convenciones de los patrones:
- amount_pattern: regex con el monto en el grupo 1. Los formatos de
  miles/decimales los resuelve parse_amount (CO/US/Bre-B).
- merchant_pattern: regex con el comercio en el grupo 1; si es None se
  usa merchant_static.
- date_pattern: regex con la fecha COMPLETA en el grupo 1, parseada
  con date_format (strptime). None → fecha de recepción del correo.
- subject_pattern: filtro por asunto — la regla solo se intenta si el
  asunto coincide (evita parsear marketing como transacciones).
- priority: orden de intento cuando un dominio tiene varias reglas.
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
        "subject_pattern": None,
        "priority": 100,
        "amount_pattern": r"\$\s*([\d.,]+)",
        "merchant_pattern": r"(?i)en\s+([A-Za-z0-9 &'.-]+?)(?:\s+el|\s*$)",
        "merchant_static": None,
        "date_pattern": None,  # sin patrón: se usa la fecha de recepción del correo
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
        "subject_pattern": None,
        "priority": 100,
        "amount_pattern": r"Total\s*[:]*\s*\$\s*([\d.,]+)",
        "merchant_pattern": None,
        "merchant_static": "Amazon",
        "date_pattern": None,
        "date_format": None,
        "currency": "COP",
        "payment_method": None,
        "suggested_category": "Compras",
    },
    # ------------------------------------------------------------------
    # BBVA — una regla por tipo de movimiento (0006). Las plantillas se
    # distinguen por ASUNTO; el comercio sale del campo Establecimiento /
    # beneficiario / factura según el tipo.
    # ------------------------------------------------------------------
    {
        # Asunto: "Compra Exitosa". Cuerpo: "... Establecimiento: Easy
        # gaitan corte Valor: $48,270.00"
        "id": "00000000-0000-4000-8000-000000000103",
        "name": "bbva_compra",
        "domains": ["bbvanet.com.co", "bbva.com.co"],
        "version": "v1",
        "subject_pattern": r"(?i)compra exitosa",
        "priority": 10,
        "amount_pattern": r"(?i)Valor:\s*\$\s*([\d.,]+)",
        "merchant_pattern": r"(?i)Establecimiento:\s*(.+?)\s+Valor:",
        "merchant_static": None,
        "date_pattern": r"(?i)Fecha de la operaci[oó]n:\s*(\d{4}-\d{2}-\d{2})",
        "date_format": "%Y-%m-%d",
        "currency": "COP",
        "payment_method": None,
        "suggested_category": None,
    },
    {
        # Asunto: "BBVA Retiro en Cajero Automatico sin Tarjeta". Cuerpo:
        # "... realizaste un retiro sin tarjeta ... por un valor de
        # $500,000.00, a través de ... Cajeros Automáticos."
        "id": "00000000-0000-4000-8000-000000000104",
        "name": "bbva_retiro",
        "domains": ["bbvanet.com.co", "bbva.com.co"],
        "version": "v1",
        "subject_pattern": r"(?i)retiro",
        "priority": 20,
        "amount_pattern": r"(?i)valor de\s*\$\s*([\d.,]+)",
        "merchant_pattern": None,
        "merchant_static": "Retiro cajero automático",
        "date_pattern": r"(?i)d[ií]a\s+(\d{4}-\d{2}-\d{2})",
        "date_format": "%Y-%m-%d",
        "currency": "COP",
        "payment_method": "efectivo",
        "suggested_category": None,
    },
    {
        # Asunto: "BBVA Móvil - Notificación de Transferencias". Cuerpo:
        # tabla "Tipo de transacción: Transferencia de BBVA a BBVA ...
        # Cuenta destino terminada en: *9425 ... Valor: $2,500,000.00".
        # El correo no trae el nombre del destinatario.
        "id": "00000000-0000-4000-8000-000000000105",
        "name": "bbva_transferencia",
        "domains": ["bbvanet.com.co", "bbva.com.co"],
        "version": "v1",
        "subject_pattern": r"(?i)notificaci[oó]n de transferencias",
        "priority": 30,
        "amount_pattern": r"(?i)Valor:\s*\$\s*([\d.,]+)",
        "merchant_pattern": r"(?i)Cuenta destino terminada en:\s*(\*\d+)",
        "merchant_static": None,
        "date_pattern": r"(?i)Fecha de la operaci[oó]n:\s*(\d{4}-\d{2}-\d{2})",
        "date_format": "%Y-%m-%d",
        "currency": "COP",
        "payment_method": None,
        "suggested_category": None,
    },
    {
        # Asunto: "Tu transferencia va en camino". Cuerpo: "Debitamos los
        # $ 843,000.00 de tu cuenta y los enviamos a Adriana Chary."
        "id": "00000000-0000-4000-8000-000000000106",
        "name": "bbva_transferencia_camino",
        "domains": ["bbvanet.com.co", "bbva.com.co"],
        "version": "v1",
        "subject_pattern": r"(?i)transferencia va en camino",
        "priority": 40,
        "amount_pattern": r"(?i)Debitamos los\s*\$\s*([\d.,]+)",
        "merchant_pattern": r"(?i)enviamos a\s+([A-Za-zÁÉÍÓÚáéíóúÑñ ]+?)\.",
        "merchant_static": None,
        "date_pattern": None,
        "date_format": None,
        "currency": "COP",
        "payment_method": None,
        "suggested_category": None,
    },
    {
        # Asunto: "BBVA Net - Pagos PSE". Cuerpo: tabla "Tipo de
        # transacción: Pago PSE ... Establecimiento: 101 FINTECH S.A
        # Valor: $18,720.00".
        "id": "00000000-0000-4000-8000-000000000107",
        "name": "bbva_pse",
        "domains": ["bbvanet.com.co", "bbva.com.co"],
        "version": "v1",
        "subject_pattern": r"(?i)pagos pse",
        "priority": 50,
        "amount_pattern": r"(?i)Valor:\s*\$\s*([\d.,]+)",
        "merchant_pattern": r"(?i)Establecimiento:\s*(.+?)\s+Valor:",
        "merchant_static": None,
        "date_pattern": r"(?i)Fecha de la operaci[oó]n:\s*(\d{4}-\d{2}-\d{2})",
        "date_format": "%Y-%m-%d",
        "currency": "COP",
        "payment_method": "pse",
        "suggested_category": None,
    },
    {
        # Asunto: "BBVA Móvil - Pago de Facturas". Cuerpo: "Realizaste un
        # pago por $30,990.00 de 5706 HOGAR Y MOVIL MOVISTAR W, referencia
        # de pago 60202071741 ... Hora 09:44 el 2026-11-20."
        "id": "00000000-0000-4000-8000-000000000108",
        "name": "bbva_facturas",
        "domains": ["bbvanet.com.co", "bbva.com.co"],
        "version": "v1",
        "subject_pattern": r"(?i)pago de facturas",
        "priority": 60,
        "amount_pattern": r"(?i)pago por\s*\$\s*([\d.,]+)",
        "merchant_pattern": r"(?i)pago por\s*\$[\d.,]+\s+de\s+(?:\d+\s+)?(.+?),\s*referencia",
        "merchant_static": None,
        "date_pattern": r"(?i)\bel\s+(\d{4}-\d{2}-\d{2})",
        "date_format": "%Y-%m-%d",
        "currency": "COP",
        "payment_method": None,
        "suggested_category": "Servicios",
    },
    {
        # Bre-B (notificacionesBreB@bbva.com). Asuntos: "El envío se
        # completó correctamente" / "Tu envío con llave fue exitoso".
        # Cuerpo: "... La llave *****5553 recibió ... Fecha y hora
        # 2026/11/23 17:17 Valor enviado $ 38.000,00". Solo Bre-B se
        # filtra de bbva.com.
        "id": "00000000-0000-4000-8000-000000000109",
        "name": "bbva_breb",
        "domains": ["bbva.com"],
        "version": "v1",
        "subject_pattern": r"(?i)env[ií]o",
        "priority": 70,
        "amount_pattern": r"(?i)Valor enviado\s*\$\s*([\d.,]+)",
        "merchant_pattern": r"(?i)llave\s+(\*+\d+)",
        "merchant_static": None,
        "date_pattern": r"(?i)Fecha y hora\s+(\d{4}/\d{2}/\d{2})",
        "date_format": "%Y/%m/%d",
        "currency": "COP",
        "payment_method": "breb",
        "suggested_category": None,
    },
]
