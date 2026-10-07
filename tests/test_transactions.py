"""Tests de idempotencia y API de transacciones (PRD §F2.6, Fase 6).

- Procesar el mismo correo dos veces jamás duplica el gasto
  (UNIQUE user_id + source_ref_id).
- Toda consulta queda filtrada por user_id (multitenant — PRD §8).
"""

import pytest


@pytest.mark.skip(reason="Fase 6: requiere BD de pruebas")
def test_insertar_mismo_source_ref_dos_veces_no_duplica():
    ...


@pytest.mark.skip(reason="Fase 6: requiere BD de pruebas")
def test_usuario_a_no_lee_transacciones_de_usuario_b():
    ...
