# Fylax — Backend (FastAPI)

API del **MVP de salud financiera automática**: ingesta de gastos 100%
automática desde el correo del usuario (Gmail API + Google Cloud Pub/Sub),
extracción con parsers deterministas (Strategy) respaldados por el motor de
IA **JEV**, sobre PostgreSQL en Supabase con procesamiento asíncrono
(Celery + Redis).

> Documento fuente del producto: [`docs/CONTEXT.md`](docs/CONTEXT.md)
> (contexto completo del aplicativo extraído del PRD v2.0).

## Stack

| Capa | Tecnología |
|-|-|
| API web | Python 3.12 + FastAPI (asyncio) |
| ORM / migraciones | SQLAlchemy 2 + Alembic |
| Base de datos | PostgreSQL gestionado en Supabase (ACID + RLS) |
| Auth | Supabase Auth (Google OAuth, JWT verificado por el backend) |
| Cola de tareas | Celery + Redis (Upstash en el MVP) |
| Correo | Gmail API + Google Cloud Pub/Sub |
| Extracción con IA | JEV (parsers deterministas primero, JEV como genérico) |
| Nube | Google Cloud Platform (Cloud Run, Pub/Sub, Secret Manager) |
| Monitoreo | Sentry + Cloud Logging |

## Arquitectura

**Monolito modular** (PRD §5.2): un solo servicio desplegable, separado por
dominios — `users`, `transactions`, `integrations (gmail)`, `billing` —
que facilita migrar a microservicios sin reescribir.

```
app/
├── main.py                  # FastAPI: incluye routers por dominio
├── core/                    # config, seguridad (JWT + AES-256-GCM), errores
├── common/                  # paginación
├── db/                      # engine, sesiones y modelos (PRD §8)
├── users/                   # POST /auth/session (Épica 1)
├── transactions/            # CRUD + filtros (Épica 3)
├── categories/              # GET /categories
├── dashboard/               # GET /dashboard/summary
├── sync/                    # GET /sync/status
├── billing/                 # límites por tier free/pro (Épica 4, sin paywall)
├── integrations/gmail/      # webhook Pub/Sub, watch, parsers, JEV (Épica 2)
└── workers/                 # Celery: process_new_email (ADR Web/Workers)
alembic/                     # migraciones versionadas
supabase/rls_policies.sql    # Row Level Security (PRD §10)
tests/                       # tests de parsers e idempotencia (Fase 6)
```

## ADR clave — Separación Web / Workers

Las llamadas a la Gmail API y a JEV pueden tardar varios segundos y
**jamás se ejecutan en el hilo del servidor web** (PRD §5.2). El webhook
`/webhooks/gmail` responde 200 en < 300 ms (F2.5) y encola
`process_new_email` en Celery (reintentos con backoff exponencial y
dead-letter). Los workers se despliegan como servicio aparte en Cloud Run
modo background o Compute Engine e2-micro.

## Puesta en marcha

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env                                 # completar variables

alembic upgrade head                                 # migraciones
uvicorn app.main:app --reload                        # API web en :8000
celery -A app.workers.celery_app worker -Q gmail     # worker de ingesta
```

Documentación interactiva (OpenAPI/Swagger) en `/docs` (PRD §9).

## Endpoints (PRD §9)

`POST /auth/session` · `POST /webhooks/gmail` · `GET|POST /transactions` ·
`PATCH|DELETE /transactions/{id}` · `GET /categories` ·
`GET /dashboard/summary` · `GET /sync/status`

Todas las rutas (excepto `/webhooks/gmail` y `/auth/session`) exigen el JWT
de Supabase Auth verificado.

## Seguridad (PRD §10)

- refresh_token de Google cifrado con AES-256-GCM (llave en Secret Manager).
- Row Level Security en Supabase (`supabase/rls_policies.sql`).
- Solo el scope `gmail.readonly` (mínimos privilegios, OAuth App Verification).
- Idempotencia: UNIQUE (user_id, source_ref_id).
- Cuerpos de correo procesados en memoria, nunca persistidos.

## Estado del proyecto

Estructura base generada desde el PRD v2.0 (23-sep-2026). Los puntos de
implementación quedaron marcados con `TODO(Fase N)` según el plan de fases
del PRD §12:

- Fases 1–4: backend base, auth, ingesta Gmail y API de consulta → **este repo**.
- Fase 5: app Flutter → repositorio `fylax_front`.
- Fase 6: endurecimiento (tests de precisión ≥ 90 %, Sentry, CI/CD, deploy a Cloud Run).
