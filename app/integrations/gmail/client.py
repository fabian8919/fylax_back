"""Cliente autenticado de la Gmail API (PRD §F2.1).

Construye un servicio de Gmail a partir del google_refresh_token del
usuario (que llega DESENCRIPTADO solo en memoria — PRD §F1.3). El
intercambio refresh_token → access_token usa el cliente OAuth web de
Google Cloud configurado por variables de entorno.

Este módulo SOLO se usa desde los workers (ADR Web/Workers — PRD §5.2):
las llamadas a Google pueden tardar segundos y jamás van en el hilo web.
"""

from google.auth.transport.requests import Request as AuthRequest
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.core.config import get_settings

# Alcance mínimo necesario (PRD §10 — privacidad): solo lectura.
GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"


def build_gmail_service(refresh_token: str):
    """Devuelve el servicio Gmail API con un access_token fresco.

    El refresh_token NUNCA se persiste ni se loguea aquí: vive solo en
    memoria durante la llamada del worker.
    """
    settings = get_settings()
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri=GOOGLE_TOKEN_URI,
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        scopes=[GMAIL_READONLY_SCOPE],
    )
    # Fuerza el intercambio refresh → access antes de construir el
    # servicio, para fallar rápido si el usuario revocó el permiso.
    creds.refresh(AuthRequest())
    return build("gmail", "v1", credentials=creds, cache_discovery=False)
