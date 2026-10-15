# Pendiente — Login Google end-to-end contra el entorno definitivo

> Estado al **15-oct-2026**. Documento operativo para retomar la sesión.
> Aplica a ambos repos: `fylax_front` (Flutter) y `fylax_back` (FastAPI).

## Lo que YA quedó hecho y verificado

- Ambos repos leen su configuración **solo del `.env`** (sin ternarios ni
  `--dart-define` en el front; `pydantic-settings` con `env_file=".env"` en
  el back).
- `fylax_front/.env`: `API_BASE_URL=http://10.0.2.2:8000/api/v1`,
  `SUPABASE_URL=https://phfprgocglekorhkapvw.supabase.co`,
  `SUPABASE_ANON_KEY=sb_publishable_...` (proyecto **definitivo**).
  `.env` registrado como asset en `pubspec.yaml` y cargado en `main.dart`
  con `flutter_dotenv`.
- `fylax_back/.env`: `SUPABASE_URL` definitivo, `SUPABASE_SECRET_KEY`
  (service role), `TOKEN_ENCRYPTION_KEY` generada (32 bytes base64),
  `DATABASE_URL` con password real → pooler `aws-0-us-east-1`.
- `fylax_back/app/core/config.py`: nuevo campo `supabase_secret_key`.
- Python 3.12.10 instalado (winget) y `fylax_back/scripts/setup.sh` creado
  (`./scripts/setup.sh [--serve]` = venv + deps + `alembic upgrade head`).
- Base de datos alineada: se dropearon 4 tablas viejas **vacías** y se aplicó
  `alembic upgrade head` limpio → `0001_initial (head)`, tablas `users`,
  `categories`, `transactions`, `email_sync_state`, `goals` + **10 categorías
  semilla**.
- API corriendo y verificada: `GET /docs` → 200, `GET /api/v1/transactions`
  sin token → **401** (verificación JWT activa).
- App Flutter corriendo en el emulador (`Medium_Phone_API_36.1`, requiere
  wipe si el disco se llena — ocurrió una vez:
  `INSTALL_FAILED_INSUFFICIENT_STORAGE` con ~474 MB libres). Pantalla de
  login renderiza OK y Supabase inicializa contra el proyecto definitivo
  (verificado en logcat: "Supabase init completed").

## Lo que FALTA para el login end-to-end

### 1. Google Cloud Console (consent screen + cliente OAuth web)

1. Proyecto de Google Cloud → APIs & Services → habilitar **Gmail API**.
2. OAuth consent screen: agregar el scope
   `https://www.googleapis.com/auth/gmail.readonly` (solo lectura — PRD §10)
   y publicar la política de privacidad (requisito de Google).
3. Credentials → crear **OAuth Client ID tipo "Web application"**.
   En "Authorized redirect URIs" agregar la URL de callback de Supabase:
   `https://phfprgocglekorhkapvw.supabase.co/auth/v1/callback`
4. Guardar el **Client ID** y **Client Secret** resultantes.

### 2. Supabase Dashboard (proyecto phfprgocglekorhkapvw)

1. Authentication → Providers → **Google**: habilitar y pegar Client ID /
   Secret del paso anterior.
2. Authentication → URL Configuration → **Redirect URLs**: agregar
   `io.supabase.flutter://login-callback` (deep link que usa la app —
   `AppConstants.oauthRedirectTo`).
3. SQL Editor → ejecutar **`fylax_back/supabase/rls_policies.sql`**
   (Row Level Security — PRD §10).

### 3. Variables pendientes en `fylax_back/.env`

```
GOOGLE_CLIENT_ID=<client-id>.apps.googleusercontent.com   # del paso 1.3
GOOGLE_CLIENT_SECRET=<client-secret>                      # del paso 1.3
GCP_PROJECT_ID=<proyecto-de-google-cloud>
JEV_API_KEY=<jev-api-key>        # solo para ingesta (Épica 2), no bloquea login
JEV_BASE_URL=<url-jev>           # idem
```

`SUPABASE_JWT_SECRET` se deja vacío a propósito: el backend verifica JWT por
JWKS público (`app/core/security.py:47`); el legacy HS256 es solo fallback.

## Cómo probar el login (checklist de verificación)

1. `cd fylax_back && ./scripts/setup.sh --serve` → API en `:8000`.
2. `cd fylax_front && flutter emulators --launch Medium_Phone_API_36.1`
   (si falla la instalación por disco, relanzar con wipe: ver nota arriba).
3. `flutter run -d emulator-5554` (sin `--dart-define`, todo viene del `.env`).
4. En el emulador: **"Continuar con Google"** → navegador → consent screen
   (debe mostrar SOLO lectura de Gmail) → autorizar → deep link devuelve a la app.
5. Verificar en la base nueva que `POST /auth/session` creó/actualizó al usuario:
   - tabla `users`: fila con el email de Google, `google_refresh_token`
     **cifrado** (AES-256-GCM, nunca texto plano — F1.3).
   - tabla `email_sync_state`: fila con `status='active'`.
6. Dashboard y feed deben cargar vacíos pero sin errores; crear una
   transacción manual y verificarla con
   `GET /api/v1/transactions` (Swagger en `http://localhost:8000/docs`).

## Notas operativas

- `10.0.2.2` en `API_BASE_URL` solo funciona desde el **emulador Android**;
  en dispositivo físico usar la IP local del PC (`http://192.168.x.x:8000/api/v1`).
- La ingesta automática (webhook Pub/Sub + workers Celery) requiere además
  Redis local y las credenciales de Google/JEV — eso es Épica 2 y no bloquea
  el login ni el CRUD manual.
- Tareas corriendo al cerrar la sesión: uvicorn (`:8000`) y el emulador son
  procesos en background; al retomar, relanzar con los pasos 1–3 de arriba.
