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

## Lo que sigue (Épica 2 — no bloquea login ni CRUD manual)

### Verificación pendiente (hacer en la app)

- Crear una transacción manual y confirmarla en
  `GET /api/v1/transactions` (Swagger en `http://localhost:8000/docs` o
  desde el mismo teléfono).
- Dashboard y feed: cargan vacíos pero sin errores.

### Variables pendientes en `fylax_back/.env` (solo para ingesta automática)

```
GOOGLE_CLIENT_ID=<client-id>.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=<client-secret>
GCP_PROJECT_ID=<proyecto-de-google-cloud>
JEV_API_KEY=<jev-api-key>
JEV_BASE_URL=<url-jev>
```

La ingesta automática (webhook Pub/Sub + workers Celery) requiere además
Redis local — no bloquea el login ni el CRUD manual.

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
