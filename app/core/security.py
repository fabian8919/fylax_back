"""Seguridad (PRD §10).

1. Verificación del JWT emitido por Supabase Auth en cada petición
   (PRD §9): todas las rutas excepto /webhooks/gmail y /auth/session
   lo exigen.
2. Cifrado AES-256-GCM del google_refresh_token de Google (PRD §F1.3):
   la llave vive en Google Secret Manager y se inyecta como variable de
   entorno; el token nunca aparece en texto plano en BD, logs ni código.
"""

import base64
import os
import uuid

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


def verify_supabase_jwt(
    token: str, settings: Settings = Depends(get_settings)
) -> CurrentUser:
    """Valida firma, emisor y expiración del JWT de Supabase Auth."""
    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail="Token inválido o expirado"
        ) from exc

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
