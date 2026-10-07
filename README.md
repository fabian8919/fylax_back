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
├── users/                   # POST /auth/session, GET|PATCH /users/me (Épica 1)
├── transactions/            # CRUD + filtros (Épica 3)
├── categories/              # GET /categories + seed del catálogo base
├── dashboard/               # GET /dashboard/summary
├── goals/                   # CRUD /goals + contribuciones (propósitos de ahorro)
├── sync/                    # GET /sync/status
├── billing/                 # límites por tier free/pro (Épica 4, sin paywall)
├── integrations/gmail/      # webhook Pub/Sub, client OAuth, watch, parsers, JEV (Épica 2)
└── workers/                 # Celery: process_new_email + renew_watches (ADR Web/Workers)
alembic/                     # migraciones versionadas (0001 = esquema + semilla)
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

alembic upgrade head                                 # migraciones + semilla de categorías
uvicorn app.main:app --reload                        # API web en :8000
celery -A app.workers.celery_app worker -Q gmail     # worker de ingesta
celery -A app.workers.celery_app beat                # renovación diaria de watches
```

Documentación interactiva (OpenAPI/Swagger) en `/docs` (PRD §9).

## Endpoints (PRD §9)

`POST /auth/session` · `GET|PATCH /users/me` · `POST /webhooks/gmail` ·
`GET|POST /transactions` · `PATCH|DELETE /transactions/{id}` ·
`GET /categories` · `GET /dashboard/summary` ·
`GET|POST /goals` · `PATCH|DELETE /goals/{id}` ·
`POST /goals/{id}/contributions` · `GET /sync/status`

Todas las rutas (excepto `/webhooks/gmail`) exigen el JWT de Supabase Auth
verificado. Montos siempre positivos: egreso/ingreso se distingue por
`Category.type`.

## Seguridad (PRD §10)

- refresh_token de Google cifrado con AES-256-GCM (llave en Secret Manager).
- Row Level Security en Supabase (`supabase/rls_policies.sql`).
- Solo el scope `gmail.readonly` (mínimos privilegios, OAuth App Verification).
- Idempotencia: UNIQUE (user_id, source_ref_id).
- Cuerpos de correo procesados en memoria, nunca persistidos.

## Estado del proyecto

Fases 1–4 del PRD §12 **implementadas y verificadas** (07-oct-2026):

- **Fase 1 — Base**: modelos completos (incl. `Goal` de propósitos de
  ahorro, presupuesto/ingreso en `User`, categorías personalizadas),
  migración `0001_initial` con esquema + semilla de categorías alineada
  con la app Flutter.
- **Fase 2 — Auth**: `/auth/session` con cifrado AES-256-GCM del refresh
  token, `GET|PATCH /users/me` (perfil + configuración financiera).
- **Fase 3 — Ingesta Gmail**: cliente OAuth (refresh→access), watch +
  renovación diaria por Celery beat, worker con historyId incremental y
  fallback de búsqueda, parsers deterministas + JEV, idempotencia por
  savepoint, `last_error` visible en `/sync/status`.
- **Fase 4 — API de consulta**: transacciones, categorías, dashboard
  (montos positivos + presupuesto del perfil), goals CRUD + abonos,
  sync status.

Verificación local: `pytest` (5 passed, 3 skipped de Fase 6), `ruff`
limpio, rutas registradas y protegidas (401 sin JWT), SQL de migración
validado en modo offline.

Pendiente:

- **Fase 5**: app Flutter → repositorio `fylax_front` (ya desarrollada).
- **Fase 6 — Endurecimiento**: tests de precisión ≥ 90 % con correos
  anonimizados, CI/CD, deploy a Cloud Run y `.env` real (Supabase,
  Redis, Google Cloud, JEV) para correr contra producción/staging.
