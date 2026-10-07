"""Webhook de Gmail: POST /webhooks/gmail (PRD §Épica 2, F2.1).

Patrón Observer (PRD §5.2): reacciona a las notificaciones push de
Google Cloud Pub/Sub. Responde HTTP 200 en MENOS de 300 ms (F2.5) y
delega todo el trabajo pesado a Celery vía Redis (ADR Web/Workers).

Seguridad (PRD §10): valida el token de verificación de Google en cada
llamada. El cuerpo es un envelope Pub/Sub con base64 en message.data
(históricamente: {emailAddress, historyId}).
"""

import base64
import json

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from app.core.config import Settings, get_settings
from app.workers.tasks.process_email import process_new_email

router = APIRouter(tags=["integrations"])


class PubSubPush(BaseModel):
    message: dict
    subscription: str


@router.post("/webhooks/gmail", status_code=status.HTTP_200_OK)
async def gmail_webhook(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    # 1. Verificación del token de Google (PRD §10).
    token = request.query_params.get("token", "")
    if token != settings.google_pubsub_verification_token:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Token inválido")

    # 2. Parseo mínimo del envelope (el cuerpo NO se procesa aquí).
    envelope = PubSubPush(**(await request.json()))
    data = json.loads(base64.b64decode(envelope["message"]["data"]).decode())

    # 3. Encolar y responder YA. Objetivo < 300 ms (F2.5).
    history_id = str(data.get("historyId", ""))
    email_address = data.get("emailAddress", "")
    process_new_email.apply_async(
        kwargs={"email_address": email_address, "history_id": history_id},
        queue="gmail",
    )
    return {"status": "queued"}
