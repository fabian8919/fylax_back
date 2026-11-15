"""Entry point del API web: `python -m app`.

Uvicorn ≥0.54 ignora la política de event loop y en Windows codifica
ProactorEventLoop a fuego en su loop factory (`uvicorn/loops/asyncio.py`)
— y psycopg async exige SelectorEventLoop. Por eso aquí se fija la
política ANTES de arrancar y se pasa a uvicorn el loop factory propio
(`app.core.loop_policy:selector_loop_factory`, SelectorEventLoop puro).

En Linux/macOS (Docker, Cloud Run) el SelectorEventLoop es igualmente
válido, así que este entry point sirve en todos los entornos.
"""

import os

from app.core.loop_policy import ensure_selector_loop_policy

ensure_selector_loop_policy()

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=os.getenv("UVICORN_HOST", "127.0.0.1"),
        port=int(os.getenv("API_PORT", "8000")),
        reload=bool(os.getenv("UVICORN_RELOAD")),
        loop="app.core.loop_policy:selector_loop_factory",
    )
