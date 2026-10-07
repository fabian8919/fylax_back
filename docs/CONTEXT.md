# Contexto del aplicativo — Fylax Backend (MVP App de Salud Financiera Automática)

> Fuente: PRD v2.0 — «PRD — MVP App de Salud Financiera Automática (SaaS)»,
> 23 de septiembre de 2026. Ingesta automatizada vía Gmail API ·
> Flutter (iOS/Android) + FastAPI + Supabase · IA: JEV · Pagos futuros: Wompi.
>
> Documento hermano: `fylax_front/docs/CONTEXT.md` (mismo contexto de
> producto, desde la perspectiva del frontend Flutter).
> Este documento consolida **todo el contexto** enfocado en lo que el
> backend (`fylax_back`) debe cumplir: épicas 1, 2 y 4 completas, y el
> contrato de API que consume el frontend en la Épica 3.

---

## 1. Visión general del producto

Aplicación móvil de salud financiera (iOS y Android) estructurada como **SaaS**.
Diferenciador frente a las apps tradicionales: la **captura 100% automática de
los gastos** — el usuario nunca digita una transacción; el sistema la detecta,
la limpia con IA y la clasifica solo.

El backend es el cerebro de esa captura: consulta la **Gmail API**, extrae
valor, comercio, fecha y medio de pago con el motor de IA **JEV** (y parsers
deterministas), y asienta la transacción en PostgreSQL (Supabase). Sobre esa
base sirve el dashboard: balance del mes, gasto por categoría y presupuesto
restante.

## 2. Objetivos del MVP y criterios de éxito (responsabilidad del backend)

1. **Objetivo 1** (< 5 min hasta primeras transacciones): login con Google vía
   Supabase Auth, scope `gmail.readonly`, POST `/auth/session` que registra al
   usuario, watch de Gmail activo y primer correo procesado.
2. **Objetivo 2** (≥ 90 % de precisión en monto y comercio): parsers Strategy
   por remitente + JEV como genérico, validado con Pydantic, medido sobre un
   set de ≥ 30 correos reales anonimizados.
3. **Objetivo 3** (cero duplicados): UNIQUE `(user_id, source_ref_id)` +
   procesamiento idempotente en el worker.
4. **Objetivo 4** (BD lista para SaaS): `subscription_tier` (free | pro) y
   `wompi_customer_id` desde el día uno, sin rediseños posteriores.

## 3. Stack del backend (PRD §4)

| Capa | Tecnología | Justificación |
|-|-|-|
| Lenguaje / framework | Python 3.12 + FastAPI | Alto rendimiento asíncrono (asyncio), ecosistema maduro de NLP e integración con IA. |
| ORM / migraciones | SQLAlchemy 2 + Alembic | Modelado relacional estricto y migraciones versionadas. |
| Base de datos | PostgreSQL en Supabase | ACID (obligatorio para dinero) + Row Level Security + panel admin incluido. |
| Auth | Supabase Auth (Google OAuth) | Emite el JWT que el backend verifica y entrega access/refresh token de Google con scope Gmail. |
| Cola | Celery + Redis | Correos y llamadas a IA en background sin bloquear el servidor web. |
| Correo | Gmail API + Google Cloud Pub/Sub | Notificaciones push de correos nuevos (canal de ingesta del MVP). |
| IA | JEV | Cuerpo del correo → JSON estructurado: comercio, valor, fecha, medio de pago. |
| Nube | Google Cloud Platform | Cloud Run, Pub/Sub, Secret Manager: integración nativa con Gmail API. |
| Pagos (futuro) | Wompi | Pasarela colombiana; esquema preparado desde ya. |
| Monitoreo | Sentry + Cloud Logging | Trazabilidad desde el día uno. |

## 4. Arquitectura del backend

### 4.1 Monolito modular (PRD §5.2)

Un solo servicio desplegable, separado internamente por dominios:
**users, transactions, integrations (gmail), billing**. Facilita migrar a
microservicios en el futuro sin reescribir. Cada dominio es un paquete con su
router FastAPI y, cuando aplica, schemas Pydantic y servicios.

### 4.2 Patrones (PRD §5.2)

- **Strategy / Factory (parsers)**: cada remitente financiero tiene su parser
  (`BancolombiaParser`, `AmazonParser`, `AviancaParser`…). Un factory elige
  por dominio del remitente; si no existe, **JEV** como parser genérico.
- **Observer / Webhooks**: `/webhooks/gmail` reacciona a Pub/Sub, responde
  200 en < 300 ms y delega a la cola.
- **DTO estricto con Pydantic**: todo cuerpo de entrada/salida validado; el
  JSON de JEV también se valida contra schema antes de tocar la BD.
- **Separación Web / Workers (ADR clave)**: Gmail API y JEV pueden tardar
  segundos; **jamás** corren en el hilo del servidor web. FastAPI encola en
  Redis, Celery procesa en background con reintentos y escalado independiente.

### 4.3 Flujo de ingesta (PRD §5.3)

1. El banco/comercio envía el recibo al correo del usuario.
2. Gmail notifica a Pub/Sub → POST al webhook del backend.
3. El backend encola `process_new_email(user_id)` en Celery y responde 200 OK.
4. El worker descarga el correo con Gmail API (refresh_token **desencriptado**,
   solo en memoria).
5. Parser correspondiente (o JEV) extrae `{merchant, amount, date, currency,
   payment_method, category}`.
6. Validación Pydantic + inserción; UNIQUE `(user_id, source_ref_id)` evita
   duplicados.

## 5. Funcionalidades críticas (backend)

### Épica 1 — Autenticación y onboarding

| ID | Backend |
|-|-|
| F1.1 | Verificación del JWT de Supabase en cada petición; 401 ante token inválido. |
| F1.2 | El scope `gmail.readonly` se solicita en el flujo OAuth del cliente; el backend registra el usuario solo con lectura. |
| F1.3 | Recibir el provider_token (refresh_token de Google) vía POST `/auth/session` y almacenarlo cifrado AES-256-GCM; llave en Secret Manager. Nunca en texto plano en BD, logs ni código. |
| F1.4 | Crear el registro `email_sync_state` inicial y registrar el watch de Gmail para que el onboarding termine con sync activa. |

### Épica 2 — Motor de ingesta automatizada (núcleo del producto)

| ID | Backend |
|-|-|
| F2.1 | Watch por usuario + renovación diaria (Cloud Scheduler + Celery beat) antes de la expiración a 7 días. Correo de prueba notifica al webhook en < 60 s. |
| F2.2 | Queries Gmail con dominios bancarios/asuntos de recibo + `historyId` incremental: correos personales o promocionales nunca generan transacciones. |
| F2.3 | System prompt estricto que exige JSON `{merchant, amount, date, currency, payment_method, suggested_category}`; validación Pydantic. Precisión ≥ 90 % sobre ≥ 30 correos anonimizados. |
| F2.4 | Parsers deterministas primero: remitentes con parser propio se procesan **sin llamada a JEV (costo cero)**. |
| F2.5 | Celery con backoff exponencial (3 reintentos), dead-letter queue y errores a Sentry. Webhook < 300 ms. |
| F2.6 | UNIQUE `(user_id, source_ref_id)`: procesar el mismo correo dos veces jamás duplica el gasto. |

### Épica 4 — Preparación SaaS con Wompi (sin paywall)

| ID | Backend |
|-|-|
| F4.1 | Campo `subscription_tier` (free \| pro) y middleware de límites: free procesa hasta N correos/mes. |
| F4.2 | Esquema compatible con Wompi (`wompi_customer_id`, estado de suscripción): activar el paywall después solo requiere poblar campos existentes y agregar el webhook de eventos de pago. |

## 6. Regla de notificaciones (PRD §7)

El backend **no genera notificaciones por gastos registrados**: el registro es
silencioso por diseño. Las push al usuario llegarán solo con recomendaciones
inteligentes y objetivos de ahorro (fases posteriores), siempre accionables,
configurables y nunca redundantes con el dashboard.

## 7. Modelo de base de datos (PRD §8)

PostgreSQL en Supabase, **multitenant** (todo cuelga de `user_id`), RLS por
tabla, montos en Decimal, unicidad para idempotencia:

| Tabla | Campos principales |
|-|-|
| `users` | id (UUID, PK, = Supabase Auth), email único, name, google_refresh_token (AES-256-GCM), subscription_tier, wompi_customer_id (nullable), created_at |
| `categories` | id, name, icon, color, type (income \| expense), is_system_default |
| `transactions` | id, user_id, category_id, amount (Numeric 10,2), currency (ISO 4217), date, merchant_clean, source (manual \| gmail_api), source_ref_id, created_at. **UNIQUE (user_id, source_ref_id)** |
| `email_sync_state` | user_id, gmail_history_id, last_sync_at, status (active \| error \| revoked) |

Las políticas RLS ejecutables están en `supabase/rls_policies.sql`.

## 8. Endpoints principales de la API (PRD §9)

| Endpoint | Método | Descripción |
|-|-|-|
| `/auth/session` | POST | Registra/actualiza el usuario desde el JWT de Supabase (incluye tokens de Google). |
| `/webhooks/gmail` | POST | Recibe push de Pub/Sub y encola el procesamiento (< 300 ms). |
| `/transactions` | GET | Lista paginada (filtros: fecha, categoría, fuente). |
| `/transactions` | POST | Crea transacción manual. |
| `/transactions/{id}` | PATCH | Edita monto, categoría o comercio. |
| `/transactions/{id}` | DELETE | Elimina una transacción. |
| `/categories` | GET | Categorías del sistema y personalizadas. |
| `/dashboard/summary` | GET | Balance del mes, gasto por categoría y presupuesto restante. |
| `/sync/status` | GET | Estado de sincronización (última actualización, errores). |

Todas las rutas excepto `/webhooks/gmail` y `/auth/session` exigen JWT de
Supabase verificado. Docs interactiva en `/docs` (FastAPI/OpenAPI).

## 9. Seguridad y cumplimiento (PRD §10)

- Tokens de Google cifrados AES-256-GCM; llaves en Secret Manager, nunca en el repo.
- RLS como segunda línea de defensa (además del filtro por user_id del backend).
- Mínimos privilegios: solo `gmail.readonly` (simplifica OAuth App Verification).
- Idempotencia y reintentos: UNIQUE + backoff; ningún gasto se cobra dos veces.
- Privacidad: cuerpos de correo procesados en memoria, no persistidos; solo la
  transacción estructurada se guarda. Política de privacidad publicada desde el MVP.
- HTTPS extremo a extremo; el webhook valida el token de verificación de Google.

## 10. Infraestructura (PRD §11)

- **API web**: Cloud Run (Docker, autoescalado 0 → N; costo cero sin tráfico).
- **Workers Celery**: Cloud Run background o Compute Engine e2-micro.
- **BD y auth**: Supabase (capa gratuita en el MVP).
- **Cola/caché**: Upstash Redis gratis; migrar a Memorystore con volumen.
- **Eventos**: Pub/Sub para notificaciones push de Gmail.
- **Secretos**: Secret Manager. **CI/CD**: GitHub Actions (lint, tests, Docker, deploy).
- **Distribución móvil**: Play Console (internas) y TestFlight antes del lanzamiento.

## 11. Plan de desarrollo por fases (PRD §12) — responsabilidad de este repo

Actuar como Staff Engineer: fases cerradas y verificables, sin mezclar capas.

1. **Fase 1 — Base del backend**: monolito modular FastAPI, modelos
   SQLAlchemy, Alembic, conexión a Supabase Postgres, entornos dev/staging/prod.
2. **Fase 2 — Autenticación**: OAuth Google vía Supabase (scope gmail.readonly),
   verificación de JWT y almacenamiento cifrado del refresh_token.
3. **Fase 3 — Ingesta Gmail**: watch + webhook Pub/Sub, lectura incremental con
   historyId, parsers Strategy y pipeline JEV validado por Pydantic, en workers
   Celery con idempotencia.
4. **Fase 4 — API de consulta**: transacciones, categorías, dashboard y sync con
   paginación y filtros.
5. **Fase 5 — App Flutter**: repositorio `fylax_front`.
6. **Fase 6 — Endurecimiento**: tests de precisión (parsers + JEV), Sentry,
   CI/CD y despliegue a Cloud Run.

Los puntos pendientes están marcados en el código con `TODO(Fase N)` y en
los tests con `@pytest.mark.skip`.

## 12. Riesgos y mitigaciones (PRD §13)

- **Verificación OAuth de Google**: scope de Gmail exige revisión de Google →
  solo lectura, política de privacidad publicada y video demo desde ya.
- **Plantillas de correo cambiantes**: parsers versionados por remitente, JEV
  como respaldo genérico y monitoreo de tasa de fallo por parser.
- **Costos de IA**: parsers deterministas primero; JEV solo para remitentes
  desconocidos o correos no resueltos.
- **Watch expira cada 7 días**: Cloud Scheduler + Celery beat renueva el watch
  de cada usuario diariamente.

---

## Anexo A — Mapa de la estructura del backend

| PRD | Paquete / archivo |
|-|-|
| F1.1–F1.3 auth + JWT + AES-256-GCM | `app/users/router.py`, `app/core/security.py` |
| F2.1 watch / renovación | `app/integrations/gmail/watch.py` |
| F2.1/F2.5 webhook Pub/Sub < 300 ms | `app/integrations/gmail/router.py` |
| F2.2 queries financieras + historyId | `app/workers/tasks/process_email.py` |
| F2.3 system prompt JEV + schema | `app/integrations/gmail/jev_client.py` |
| F2.4 parsers Strategy / Factory | `app/integrations/gmail/parsers/` |
| F2.5 cola, backoff, dead-letter, Sentry | `app/workers/celery_app.py` |
| F2.6 UNIQUE idempotencia | `app/db/models.py` (`Transaction`) |
| Épica 3 contrato API | `app/transactions/`, `app/dashboard/`, `app/categories/`, `app/sync/` |
| F4.1–F4.2 tiers y Wompi | `app/billing/router.py`, `app/db/models.py` (`User`) |
| §8 modelo de datos | `app/db/models.py` + migraciones Alembic |
| §10 RLS | `supabase/rls_policies.sql` |
| §11 despliegue | `Dockerfile`, `.github/workflows/ci.yml` |
