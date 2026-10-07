"""Punto de entrada del API web (FastAPI).

Monolito modular (PRD §5.2): un solo servicio desplegable separado por
dominios — users, transactions, integrations (gmail), billing — que
facilita migrar a microservicios sin reescribir.

ADR clave — separación Web / Workers: las llamadas a la Gmail API y a
JEV pueden tardar varios segundos y JAMÁS se ejecutan en este hilo; se
encolan en Redis y Celery las procesa en background (PRD §5.2).
"""

import sentry_sdk
from fastapi import FastAPI

from app.core.config import get_settings
from app.routers import api_router

settings = get_settings()

# Trazabilidad de errores desde el día uno (PRD §4 — Sentry).
if settings.sentry_dsn:
    sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.env)

app = FastAPI(
    title="Fylax API",
    description="MVP de salud financiera automática — ingesta vía Gmail API + IA JEV.",
    version="0.1.0",
    # Documentación interactiva automática en /docs (PRD §9).
    docs_url="/docs",
    openapi_url="/openapi.json",
)

app.include_router(api_router, prefix="/api/v1")
