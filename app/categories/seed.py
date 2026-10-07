"""Semilla de categorías del sistema (PRD §8 — is_system_default).

Los nombres, iconos y colores están ALINEADOS con la app Flutter
(material symbols + paleta azul/verde/negra de Fylax). Los UUIDs son
fijos para que la migración y los entornos compartan los mismos ids.

La migración 0001 importa esta lista: mantenerla como ÚNICA fuente de
verdad del catálogo base.
"""

#: Cada entrada: id fijo, nombre, icono (material symbol), color hex, tipo.
DEFAULT_CATEGORIES: list[dict[str, str]] = [
    {
        "id": "00000000-0000-4000-8000-000000000001",
        "name": "Domicilios",
        "icon": "delivery",
        "color": "#2E8FFF",
        "type": "expense",
    },
    {
        "id": "00000000-0000-4000-8000-000000000002",
        "name": "Restaurantes",
        "icon": "restaurant",
        "color": "#34E0A1",
        "type": "expense",
    },
    {
        "id": "00000000-0000-4000-8000-000000000003",
        "name": "Mercado",
        "icon": "groceries",
        "color": "#00D68F",
        "type": "expense",
    },
    {
        "id": "00000000-0000-4000-8000-000000000004",
        "name": "Transporte",
        "icon": "transport",
        "color": "#1E5EFF",
        "type": "expense",
    },
    {
        "id": "00000000-0000-4000-8000-000000000005",
        "name": "Suscripciones",
        "icon": "subscriptions",
        "color": "#5EB2FF",
        "type": "expense",
    },
    {
        "id": "00000000-0000-4000-8000-000000000006",
        "name": "Salud",
        "icon": "health",
        "color": "#7BE8C3",
        "type": "expense",
    },
    {
        "id": "00000000-0000-4000-8000-000000000007",
        "name": "Entretenimiento",
        "icon": "entertainment",
        "color": "#8FB8DE",
        "type": "expense",
    },
    {
        "id": "00000000-0000-4000-8000-000000000008",
        "name": "Servicios",
        "icon": "services",
        "color": "#3ECF8E",
        "type": "expense",
    },
    {
        "id": "00000000-0000-4000-8000-000000000009",
        "name": "Ingresos",
        "icon": "income",
        "color": "#00D68F",
        "type": "income",
    },
    {
        # Fallback cuando JEV sugiere una categoría desconocida.
        "id": "00000000-0000-4000-8000-000000000010",
        "name": "Otros",
        "icon": "category",
        "color": "#5C6B7A",
        "type": "expense",
    },
]

#: Nombre de la categoría fallback para la ingesta automática.
FALLBACK_CATEGORY_NAME = "Otros"
