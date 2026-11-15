"""Compatibilidad del event loop de asyncio en Windows.

psycopg (driver async de PostgreSQL) NO soporta el ProactorEventLoop que
Python usa por defecto en Windows desde la 3.8 — exige el
SelectorEventLoop. Uvicorn ≥0.49 ya no fuerza la política por su cuenta,
y además importa la app dentro del event loop ya creado, así que fijarla
en app/main.py queda tarde para el API web; los `asyncio.run()` de los
workers de Celery y los scripts locales correrían con Proactor y
fallarían con:

    psycopg.InterfaceError: Psycopg cannot use the 'ProactorEventLoop'
    to run in async mode.

Llamar a `ensure_selector_loop_policy()` al inicio de cada entry point
(`python -m app`, celery_app, scripts) fija la política correcta en
Windows antes de crear el loop; es un no-op en Linux/macOS.

Detalle uvicorn ≥0.54: su loop factory (`uvicorn/loops/asyncio.py`)
codifica ProactorEventLoop en Windows a fuego e IGNORA la política, así
que para el API web no basta con la política — `python -m app` le pasa
además `selector_loop_factory` como `--loop`.
"""

import asyncio
import sys


def ensure_selector_loop_policy() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def selector_loop_factory(
    use_subprocess: bool = False,  # noqa: ARG001 — compat con firma de uvicorn
) -> asyncio.AbstractEventLoop:
    """Loop factory Selector para `--loop` de uvicorn (psycopg async).

    Contrato: para `--loop` con ruta punteada custom, uvicorn NO llama a
    esta función con `use_subprocess`; el Runner de asyncio la llama una
    sola vez sin argumentos y espera la INSTANCIA del loop (los factories
    builtin de uvicorn devuelven la clase porque uvicorn sí los llama).
    """
    return asyncio.SelectorEventLoop()
