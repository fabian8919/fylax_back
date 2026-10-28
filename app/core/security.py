"""Seguridad (PRD §10).

1. Verificación del JWT emitido por Supabase Auth en cada petición
   (PRD §9): todas las rutas excepto /webhooks/gmail lo exigen.

   Supabase migró a llaves de firma asimétricas (ECC P-256 / ES256) con
   rotación: la verificación se hace contra el JWKS público del proyecto
   (`<SUPABASE_URL>/auth/v1/.well-known/jwks.json`), que PyJWKClient
   cachea y refresca ante rotaciones. Como fallback se acepta el legacy
   JWT secret (HS256) para proyectos que aún no han migrado.

2. Cifrado AES-256-GCM del google_refresh_token de Google (PRD §F1.3):
   la llave vive en Google Secret Manager y se inyecta como variable de
   entorno; el token nunca aparece en texto plano en BD, logs ni código.
"""

import base64
import os
import uuid
from typing import Any

import jwt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.core.config import Settings, get_settings

_bearer = HTTPBearer(auto_error=False)


class CurrentUser(BaseModel):
    """Identidad del usuario autenticado (sub del JWT de Supabase)."""

    id: uuid.UUID
    email: str


#: Cliente JWKS cacheado a nivel de módulo (thread-safe y con caché
#: interno de llaves; se instancia perezosamente al primer uso).
_jwks_client: jwt.PyJWKClient | None = None


def _get_jwks_client(settings: Settings) -> jwt.PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        jwks_url = f"{settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
        _jwks_client = jwt.PyJWKClient(jwks_url, cache_keys=True)
    return _jwks_client


def _decode_via_jwks(token: str, settings: Settings) -> dict[str, Any]:
    """Verifica con las llaves públicas de Supabase (ES256 y sucesoras)."""
    signing_key = _get_jwks_client(settings).get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["ES256", "RS256", "EdDSA"],
        audience="authenticated",
    )


def _decode_via_legacy_secret(token: str, settings: Settings) -> dict[str, Any]:
    """Fallback HS256 con el legacy JWT secret (proyectos sin migrar)."""
    return jwt.decode(
        token,
        settings.supabase_jwt_secret,
        algorithms=["HS256"],
        audience="authenticated",
    )


def verify_supabase_jwt(
    token: str, settings: Settings = Depends(get_settings)
) -> CurrentUser:
    """Valida firma, audiencia y expiración del JWT de Supabase Auth."""
    payload: dict[str, Any] | None = None

    if settings.supabase_url:
        try:
            payload = _decode_via_jwks(token, settings)
        except jwt.PyJWTError:
            payload = None  # intenta el fallback legacy

    if payload is None and settings.supabase_jwt_secret:
        try:
            payload = _decode_via_legacy_secret(token, settings)
        except jwt.PyJWTError:
            payload = None

    if payload is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail="Token inválido o expirado"
        )

    return CurrentUser(
        id=uuid.UUID(payload["sub"]),
        email=payload.get("email", ""),
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(get_settings),
) -> CurrentUser:
    """Dependencia FastAPI: exige JWT válido de Supabase (PRD §F1.1)."""
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Falta el token")
    return verify_supabase_jwt(credentials.credentials, settings)


class TokenCipher:
    """AES-256-GCM para el google_refresh_token (PRD §F1.3)."""

    def __init__(self, key_b64: str) -> None:
        key = base64.b64decode(key_b64)
        if len(key) != 32:
            raise ValueError("TOKEN_ENCRYPTION_KEY debe ser 32 bytes en base64")
        self._aead = AESGCM(key)

    def encrypt(self, plaintext: str) -> str:
        nonce = os.urandom(12)
        ct = self._aead.encrypt(nonce, plaintext.encode(), None)
        return base64.b64encode(nonce + ct).decode()

    def decrypt(self, blob_b64: str) -> str:
        raw = base64.b64decode(blob_b64)
        nonce, ct = raw[:12], raw[12:]
        return self._aead.decrypt(nonce, ct, None).decode()


def get_token_cipher(settings: Settings = Depends(get_settings)) -> TokenCipher:
    return TokenCipher(settings.token_encryption_key)
