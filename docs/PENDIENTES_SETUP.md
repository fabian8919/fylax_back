# Pendiente — Login Google end-to-end contra el entorno definitivo

> Estado al **14-nov-2026**. Documento operativo para retomar la sesión.
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

### Variables pendientes en `fylax_back/.env`

```
JEV_API_KEY=<jev-api-key>
JEV_BASE_URL=<url-jev>
```

## Notas operativas

- `10.0.2.2` en `API_BASE_URL` solo funciona desde el **emulador Android**;
  en dispositivo físico usar la IP local del PC
  (`http://192.168.1.12:8000/api/v1` en la red actual — cambia si cambia
  la red).
- Levantar el back: `python -m app` (o `./scripts/setup.sh --serve`).
  Nunca `uvicorn app.main:app` directo en Windows (rompe psycopg async).
- `SUPABASE_JWT_SECRET` se deja vacío a propósito: el backend verifica JWT
  por JWKS público (`app/core/security.py:47`); el legacy HS256 es solo
  fallback.
