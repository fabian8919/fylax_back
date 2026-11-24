# Pendiente — Login Google end-to-end contra el entorno definitivo

> Estado al **23-nov-2026**. Documento operativo para retomar la sesión.
> Aplica a ambos repos: `fylax_front` (Flutter) y `fylax_back` (FastAPI).

## ✅ Login end-to-end: VERIFICADO (14-nov-2026)

Flujo completo probado en teléfono físico (Xiaomi Mi 10T, MIUI) contra el
proyecto definitivo de Supabase (`phfprgocglekorhkapvw`):

1. OAuth de Google en Chrome → consent screen `gmail.readonly` → deep link
   `io.supabase.flutter://login-callback` de vuelta a la app.
2. `POST /api/v1/auth/session` → 200: usuario creado en `users` con
   `google_refresh_token` **cifrado** (AES-256-GCM) y fila `email_sync_state`
   con `status='active'` (verificado en la base: 2 usuarios de prueba).
3. RLS aplicado: 8 políticas activas en `pg_policies` (users, transactions,
   categories, email_sync_state).

### Arreglos aplicados el 14-nov

**fylax_front**:
- `android/app/src/debug/AndroidManifest.xml`: `usesCleartextTraffic="true"`
  (solo debug) — requerido para hablar con el back por HTTP en la LAN.
- `.env`: `SUPABASE_URL`/`SUPABASE_ANON_KEY` reales y
  `API_BASE_URL=http://<IP-LAN-del-PC>:8000/api/v1` (**con** el prefijo
  `/api/v1`). Recuerda: el `.env` se empaqueta al compilar; tras editarlo
  hay que hacer `flutter run` completo (el hot reload no lo recarga).

**fylax_back**:
- **Fix Windows/psycopg**: uvicorn 0.54 ignora la política de event loop y
  codifica `ProactorEventLoop`, incompatible con psycopg async (causaba 500
  en TODOS los endpoints con DB). Solución:
  - `app/core/loop_policy.py`: `selector_loop_factory` (devuelve la
    **instancia** — para `--loop` custom uvicorn no la llama con
    `use_subprocess`; el Runner la invoca sin args).
  - `app/__main__.py`: entry point `python -m app` que fija la política y
    pasa `loop="app.core.loop_policy:selector_loop_factory"`.
  - `scripts/setup.sh`: levanta el API con `python -m app` (con
    `UVICORN_HOST=0.0.0.0 UVICORN_RELOAD=1`).
- **Merge incompleto reparado**: `app/alerts/router.py` y
  `app/goals/monitoring.py` importaban `PlanAlert`, que no existía en
  `app/db/models.py` (el merge trajo la migración 0003 pero no el modelo,
  y olvidó registrar el router). Agregado el modelo `PlanAlert` a
  `models.py` y `alerts_router` a `app/routers.py`. `/api/v1/alerts`,
  `/goals` y `/sync/status` ya responden 401 (antes 404/500).
- `PATCH /users/me`: acepta `income_amount`/`income_frequency` (lo que el
  front siempre envió y pydantic ignoraba en silencio) y deriva
  `monthly_income` (quincenal ×2, misma regla que el demo del front);
  `UserResponse` incluye ambos campos.
- Tests: 14 passed, 3 skipped.

## Lo que sigue (Épica 2 — ingesta automática)

### Estado al 17-nov-2026: pipeline E2E funcionando

Verificado en vivo: webhook → Pub/Sub (simulado) → Redis (Upstash) →
worker Celery → Gmail API → correo encontrado → tarea `succeeded`.

- Configurado en `.env`: `GCP_PROJECT_ID`, `GOOGLE_PUBSUB_VERIFICATION_TOKEN`
  y `REDIS_URL` (Upstash, `rediss://` con TLS).
- Túnel público con cloudflared (`cloudflared tunnel --url
  http://localhost:8000`) → suscripción push de Pub/Sub apuntando a
  `https://<túnel>/api/v1/webhooks/gmail?token=<GOOGLE_PUBSUB_VERIFICATION_TOKEN>`.
  **Ojo**: la URL del túnel cambia si se reinicia cloudflared → actualizar
  la suscripción.
- Watches de Gmail registrados para ambos usuarios de prueba (expiran a los
  7 días; el beat los renueva a diario a las 4:17).
- **Fixes aplicados**:
  - `app/workers/celery_app.py`: kombu exige `ssl_cert_reqs` EN LA URL
    rediss:// (no basta `broker_use_ssl`) — se normaliza la URL.
  - `app/integrations/gmail/jev_client.py`: JEV ahora es OPCIONAL — sin
    credenciales, los correos sin parser determinista se ignoran con un
    warning en vez de romper la tarea.
  - `app/workers/tasks/process_email.py`: el manejador de errores usa una
    sesión NUEVA para registrar el fallo (la sesión original puede quedar
    en estado MissingGreenlet tras una excepción a mitad del pipeline).

### Pendiente

- **JEV** (`JEV_API_KEY`/`JEV_BASE_URL`) o parser determinista para remitentes
  sin parser: la query financiera incluye `nequi.com.co` pero NO hay
  `NequiParser` — hoy esos correos se ignoran (warning) en vez de parsearse.
- Levantar los procesos en cada sesión de desarrollo:
  `python -m app` (API), cloudflared (túnel),
  `celery -A app.workers.celery_app worker -Q gmail --pool=solo`
  (en Windows el pool prefork no funciona — usar `--pool=solo`),
  `celery -A app.workers.celery_app beat`.
- Prueba real: llegada de una alerta de Bancolombia/Amazon/Avianca al
  correo → debe aparecer como transacción en la app.
- Consent screen en modo Testing: el refresh token expira a los 7 días;
  publicar el consent screen lo evita.

### Últimos ajustes (17-nov-2026)

- `.gitignore`: ignorados `celerybeat-schedule.*` (los genera el beat al
  correr en local).
- App instalada en el teléfono físico (Xiaomi, MIUI) vía
  `adb install -r build\app\outputs\flutter-apk\app-debug.apk`.
  MIUI exige activar **"Instalar mediante USB"** en Opciones de
  desarrollador y confirmar el diálogo en pantalla; sin eso falla con
  `INSTALL_FAILED_USER_RESTRICTED`.
- Recordatorio: la app (instalada o en `flutter run`) necesita los 4
  procesos del back corriendo (API, túnel, worker, beat) y el teléfono en
  la misma WiFi del PC; el `.env` se empaqueta en el APK al compilar.

### Variables pendientes en `fylax_back/.env`

```
JEV_API_KEY=<jev-api-key>
JEV_BASE_URL=<url-jev>
```

## Notas operativas

- `10.0.2.2` en `API_BASE_URL` solo funciona desde el **emulador Android**;
  en dispositivo físico usar la IP local del PC
  (`http://192.168.1.15:8000/api/v1` en la red actual — **cambia si el
  router reasigna**; solución: reserva DHCP en el router para la MAC del
  PC, o el despliegue de abajo).
- Levantar el back: `python -m app` (o `./scripts/setup.sh --serve`).
  Nunca `uvicorn app.main:app` directo en Windows (rompe psycopg async).
- `SUPABASE_JWT_SECRET` se deja vacío a propósito: el backend verifica JWT
  por JWKS público (`app/core/security.py:47`); el legacy HS256 es solo
  fallback.

## Estado al 23-nov-2026: parseo dinámico + realtime + fechas reales

Sesión de ingesta en vivo verificada end-to-end (correo reenviado →
webhook → worker → transacción visible en la app sin refrescar).

**fylax_back**:
- **Regex dinámicas**: tabla `parser_rules` (migración 0004) — las regex
  de los parsers ya no están quemadas en código. `RuleParser` genérico
  construido desde la fila; caché de 5 min en el worker; fallback a la
  semilla (`parsers/seed.py`) si la tabla está vacía. Flags inline
  (`(?i)`), montos formato COP. Editar una fila en Supabase = cambio en
  caliente sin desplegar.
- **Query de Gmail dinámica**: tabla `app_settings` (0005) clave/valor
  (`app/core/db_settings.py`); `gmail_financial_query` (fallback cuando
  expira el historyId) editable en BD. Incluye `gmail.com` mientras
  duren las pruebas de reenvío.
- **Fix idempotencia (worker)**: commit por mensaje en vez de savepoint
  — con el driver async, un IntegrityError en `begin_nested` dejaba la
  sesión en PendingRollbackError y tumbaba el lote entero. Además
  `user.id`/`start_history_id` se capturan como valores planos: tras un
  rollback el ORM queda expirado y el acceso lazy lanzaba
  MissingGreenlet que ENMASCARABA el error real en los logs.
- **Fix fechas**: la transacción usa la fecha de recepción del correo
  (`internalDate` → hora America/Bogota) cuando la regla no extrae fecha
  del cuerpo; antes era `date.today()` y el feed quedaba desorganizado
  al reprocesar. Fallback de búsqueda: maxResults 10 → 50.
- Tests: 18 passed, 3 skipped. Ruff limpio salvo E402 preexistente en
  `app/__main__.py`.

**fylax_front**:
- **Tiempo real**: `transactions` agregada a la publicación
  `supabase_realtime` (SQL directo, RLS filtra por usuario). Provider
  `realtime_provider.dart` suscrito a INSERTs → invalida
  dashboard/movimientos/propósitos/alertas: el movimiento aparece solo,
  sin pull-to-refresh. Enganchado en DashboardScreen y
  TransactionsFeedScreen. APK recompilada e instalada vía adb.

**Re-importación de datos de prueba**: borrados los movimientos
`gmail_api` con fecha de ingesta y re-importados con fecha real
(reset de `email_sync_state.gmail_history_id` a NULL + tarea encolada
manual + query temporalmente sin filtro de asunto, ya restaurada).

### Pendiente

- **REVISAR: fechas y monto en el resumen (dashboard)** — lo notó el
  usuario al final de la sesión: con las fechas corregidas los montos se
  mueven entre meses, y los falsos positivos inflan el "Gasto del mes"
  (correos de marketing de BBVA parseados como compras: "tus viajes"
  $30M ×2, "tu Cuenta BBVA" $49.5M, "en cuenta que…" $20.000 con
  comercio basura). Verificar que `GET /dashboard/summary` agregue bien
  por mes y limpiar los falsos positivos desde la app.
- **Precisión de parsers (Fase 6)**: los regex de BBVA/Bancolombia
  matchean correos de marketing como si fueran compras. Iterar las
  reglas directo en `parser_rules` (sin desplegar) con el set de correos
  anonimizados hasta ≥90% de precisión.
- **Quitar `gmail.com`** de la regla `bancolombia` en `parser_rules` y
  de `gmail_financial_query` al pasar a producción (es temporal para
  pruebas de reenvío).
- **RLS de tablas nuevas**: las políticas de `parser_rules` y
  `app_settings` están en `supabase/rls_policies.sql` pero se aplican a
  mano en el SQL Editor de Supabase.
- **Usuario `ing.felipepadilla@gmail.com` con `invalid_grant`** (refresh
  token expirado/revocado — consent screen en Testing expira a los 7
  días): re-login en la app para renovarlo; sus tareas viejas en Redis
  drenan solas con error.
- **Cuota Gmail API**: la tormenta de reintentos agotó el límite por
  minuto (`rateLimitExceeded`); con los fixes ya no hay bucle, pero ojo
  al re-importar lotes grandes.

## Fase 6 — Despliegue: que el back no dependa del PC (PRD §11)

Ya está en la nube: **Supabase** (DB), **Upstash** (Redis/Celery) y
**Pub/Sub**. Falta mover los procesos que hoy corren en el PC:

1. **API web → Cloud Run** (el `Dockerfile` ya está listo):
   ```
   gcloud builds submit --tag us-east1-docker.pkg.dev/<proyecto>/fylax/api
   gcloud run deploy fylax-api --image ... --region us-east1
   ```
   URL HTTPS permanente (adiós túnel efímero y HTTP en claro), escala a 0
   sin tráfico → free tier. Los secretos del `.env` van en
   **Secret Manager** (DATABASE_URL, TOKEN_ENCRYPTION_KEY, REDIS_URL…).
2. **Workers Celery (worker + beat) → Compute Engine e2-micro** (free
   tier): son procesos persistentes; Cloud Run no sirve para eso. VM con
   repo + `.env` + systemd.
3. **Reapuntar las puntas**:
   - Suscripción push de Pub/Sub → URL permanente de Cloud Run.
   - `API_BASE_URL` del front → URL de Cloud Run (HTTPS).
   - Completar el job `deploy` de `.github/workflows/ci.yml` (TODO) con
     Workload Identity Federation para desplegar en cada push a `main`.

**Requisitos del usuario**: habilitar facturación en el proyecto de
Google Cloud (no cobra dentro del free tier), instalar gcloud CLI
(`winget install Google.CloudSDK`) y confirmar el project ID.
