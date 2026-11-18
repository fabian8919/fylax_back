#!/usr/bin/env bash
# Levanta el entorno de desarrollo completo del back (Épica 2).
#
#   ./scripts/dev_up.sh
#
# Inicia los 4 procesos en background con logs en ./logs/ y muestra la
# URL del túnel. Al reiniciar el PC hay que revisar:
#   1. La URL del túnel (cambia cada vez) → actualizar la suscripción
#      push en Pub/Sub si cambió.
#   2. La IP del PC (ipconfig) → si cambió, actualizar API_BASE_URL en
#      el .env del front y recompilar la app.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p logs

PY=".venv/Scripts/python.exe"
CLOUDFLARED="/c/Program Files (x86)/cloudflared/cloudflared.exe"

echo ">> API web (0.0.0.0:8000)..."
UVICORN_HOST=0.0.0.0 "$PY" -m app > logs/api.log 2>&1 &
echo $! > logs/api.pid

echo ">> Túnel cloudflared..."
"$CLOUDFLARED" tunnel --url http://localhost:8000 > logs/tunel.log 2>&1 &
echo $! > logs/tunel.pid

echo ">> Worker Celery (cola gmail)..."
"$PY" -m celery -A app.workers.celery_app worker -Q gmail --pool=solo \
  --loglevel=info > logs/worker.log 2>&1 &
echo $! > logs/worker.pid

echo ">> Beat Celery..."
"$PY" -m celery -A app.workers.celery_app beat --loglevel=info \
  > logs/beat.log 2>&1 &
echo $! > logs/beat.pid

echo ">> Esperando la URL del túnel..."
for _ in $(seq 1 15); do
  TUNEL=$(grep -o "https://[a-z0-9-]*\.trycloudflare\.com" logs/tunel.log | head -1 || true)
  [ -n "$TUNEL" ] && break
  sleep 1
done

echo
echo "Listo. PIDs en logs/*.pid, logs en logs/*.log"
echo "Túnel:  ${TUNEL:-NO ARRANCÓ — revisa logs/tunel.log}"
echo "Webhook para Pub/Sub: ${TUNEL}/api/v1/webhooks/gmail?token=<GOOGLE_PUBSUB_VERIFICATION_TOKEN>"
echo "IP del PC para el .env del front:"
ipconfig //all 2>/dev/null | grep -i "ipv4" | grep -o "[0-9.]*" | head -3
