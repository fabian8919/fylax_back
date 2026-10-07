"""Watch de Gmail API por usuario (PRD §F2.1).

Se registra un watch sobre la bandeja de entrada de cada usuario y se
renueva antes de su expiración (7 días). La renovación es una tarea
programada diaria (Cloud Scheduler + Celery beat — PRD §13).

Costo: el watch habilita las notificaciones push vía Pub/Sub; el backend
NO hace polling de la bandeja.
"""

from app.integrations.gmail.client import build_gmail_service

# Tipo de notificación push hacia Pub/Sub (PRD §Épica 2, paso 2).
TOPIC_NAME_TEMPLATE = "projects/{project}/topics/{topic}"
LABEL_ID_INBOX = "INBOX"


def register_watch(
    refresh_token: str,
    project_id: str,
    topic: str,
) -> dict:
    """Registra (o renueva) el watch de Gmail del usuario.

    El refresh_token llega DESENCRIPTADO desde el worker (se descifra con
    TokenCipher justo antes de llamar a la Gmail API — PRD §F2.1/F1.3).
    """
    service = build_gmail_service(refresh_token)
    request = {
        "labelIds": [LABEL_ID_INBOX],
        "topicName": TOPIC_NAME_TEMPLATE.format(project=project_id, topic=topic),
    }
    # Expira en 7 días (renovar diariamente — PRD §13).
    return service.users().watch(userId="me", body=request).execute()
