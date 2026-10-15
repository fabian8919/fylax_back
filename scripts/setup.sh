#!/usr/bin/env bash
# setup.sh — puesta en marcha del backend Fylax en un solo comando.
#
# Uso:
#   ./scripts/setup.sh           # venv + dependencias + migraciones
#   ./scripts/setup.sh --serve   # lo anterior y levanta la API en :8000
#
# Pensado para Git Bash en Windows (también funciona en Linux/macOS).
# Requisitos previos: Python >= 3.12 instalado y .env completo (ver
# .env.example). Las RLS policies de supabase/rls_policies.sql se aplican
# aparte, desde el SQL Editor de Supabase (PRD §10).

set -euo pipefail
cd "$(dirname "$0")/.."

SERVE=false
for arg in "$@"; do
  case "$arg" in
    --serve) SERVE=true ;;
    *) echo "Uso: $0 [--serve]"; exit 1 ;;
  esac
done

info() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
err()  { printf '\033[1;31mERROR:\033[0m %s\n' "$*" >&2; }

# --- 1. Localizar Python >= 3.12 -----------------------------------------
find_python() {
  local candidates=("py -3.12" "python" "python3")
  for candidate in "${candidates[@]}"; do
    # shellcheck disable=SC2086
    if $candidate -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)' 2>/dev/null; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

info "Buscando Python >= 3.12..."
if ! PYTHON=$(find_python); then
  err "No se encontró Python 3.12+."
  echo "  Instálalo desde https://www.python.org/downloads/ (marca 'Add to PATH')" >&2
  echo "  o con: winget install Python.Python.3.12" >&2
  exit 1
fi
info "Usando: $PYTHON ($($PYTHON --version 2>&1))"

# --- 2. Verificar .env -----------------------------------------------------
if [ ! -f .env ]; then
  err "Falta el archivo .env"
  echo "  Cópialo y complétalo: cp .env.example .env" >&2
  exit 1
fi

# --- 3. Entorno virtual ----------------------------------------------------
if [ ! -d .venv ]; then
  info "Creando entorno virtual (.venv)..."
  $PYTHON -m venv .venv
fi

# Git Bash en Windows usa Scripts/; Unix usa bin/.
if [ -f .venv/Scripts/activate ]; then
  source .venv/Scripts/activate
else
  source .venv/bin/activate
fi

# --- 4. Dependencias --------------------------------------------------------
info "Instalando dependencias (pip install -e \".[dev]\")..."
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -e ".[dev]"

# --- 5. Migraciones ----------------------------------------------------------
info "Aplicando migraciones (alembic upgrade head)..."
alembic upgrade head

info "Setup completo."
echo
echo "  API web:        uvicorn app.main:app --reload        # http://localhost:8000/docs"
echo "  Worker Gmail:   celery -A app.workers.celery_app worker -Q gmail"
echo "  Beat (watches): celery -A app.workers.celery_app beat"
echo
echo "  Recordatorio: aplica supabase/rls_policies.sql en el SQL Editor de"
echo "  Supabase (RLS — PRD §10) y ten Redis corriendo para los workers."

# --- 6. Servir (opcional) ----------------------------------------------------
if [ "$SERVE" = true ]; then
  info "Levantando API en http://localhost:8000 ..."
  exec uvicorn app.main:app --reload --port 8000
fi
