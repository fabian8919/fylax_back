"""Fixtures compartidas de los tests (pytest).

TODO(Fase 6): levantar PostgreSQL efímero (testcontainers) o usar
Supabase branch. Por ahora: app FastAPI con BD en memoria deshabilitada.

Las variables de entorno se fijan ANTES de importar la app: el engine
de SQLAlchemy se crea en import-time y exige una DATABASE_URL válida.
"""

import base64
import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault(
    "TOKEN_ENCRYPTION_KEY", base64.b64encode(b"0" * 32).decode()
)
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-secret")

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
