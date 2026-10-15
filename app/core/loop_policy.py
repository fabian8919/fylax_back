"""Compatibilidad del event loop de asyncio en Windows.

psycopg (driver async de PostgreSQL) NO soporta el ProactorEventLoop que
Python usa por defecto en Windows desde la 3.8 — exige el
SelectorEventLoop. Uvicorn ya fuerza la política correcta al arrancar,
pero los `asyncio.run()` de los workers de Celery y los scripts locales
correrían con Proactor y fallarían con:

    psycopg.InterfaceError: Psycopg cannot use the 'ProactorEventLoop'
    to run in async mode.

Llamar a `ensure_selector_loop_policy()` al inicio de cada entry point
(main web, celery_app, scripts) fija la política correcta en Windows y
es un no-op en Linux/macOS.
"""

import asyncio
import sys


def ensure_selector_loop_policy() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
