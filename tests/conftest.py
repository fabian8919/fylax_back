"""Fixtures compartidas de los tests (pytest).

TODO(Fase 6): levantar PostgreSQL efímero (testcontainers) o usar
Supabase branch. Por ahora: app FastAPI con BD en memoria deshabilitada.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
