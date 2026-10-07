"""App Celery: cola de tareas en background (PRD §4, §5.2).

ADR clave — separación Web / Workers: las llamadas a la Gmail API y a
JEV pueden tardar varios segundos y jamás se ejecutan en el hilo del
servidor web. Este proceso es un servicio aparte (Cloud Run background
o Compute Engine e2-micro — PRD §11).

Configuración (PRD §F2.5):
- reintentos con backoff exponencial (max 3),
- dead-letter queue para correos fallidos,
- errores reportados a Sentry.
"""

from celery import Celery
from celery.schedules import crontab
from celery.signals import task_failure

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "fylax",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.workers.tasks.process_email",
        "app.workers.tasks.renew_watches",
    ],
)

celery_app.conf.update(
    task_default_queue="default",
    task_routes={"app.workers.tasks.process_email.*": {"queue": "gmail"}},
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Backoff exponencial: 1 min, 4 min, 16 min (F2.5).
    task_time_limit=300,
    # Dead-letter: tras agotar reintentos, la tarea queda registrada
    # (failed state en Redis) y se notifica a Sentry.
    # Renovación diaria de watches de Gmail (expiran a los 7 días — §13).
    beat_schedule={
        "renew-gmail-watches-daily": {
            "task": "app.workers.tasks.renew_watches.renew_gmail_watches",
            "schedule": crontab(hour=4, minute=17),
        },
    },
)


@task_failure.connect
def report_task_failure(
    sender=None, task_id=None, exception=None, *args, **kwargs
) -> None:
    """Registro de errores en Sentry (PRD §F2.5)."""
    import sentry_sdk

    if settings.sentry_dsn:
        sentry_sdk.capture_exception(exception)
