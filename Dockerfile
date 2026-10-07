# Imagen base: Python 3.12 slim (PRD §4)
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencias primero para aprovechar la caché de capas de Docker
COPY pyproject.toml ./
RUN pip install .

COPY . .

EXPOSE 8000

# API web en Cloud Run (PRD §11 — autoescalado 0 → N instancias).
# Los workers Celery se despliegan como servicio aparte en modo background
# (Cloud Run background o Compute Engine e2-micro — ADR separación Web/Workers).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
