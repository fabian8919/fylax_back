"""Configuración de entornos (dev/staging/prod — PRD §12 Fase 1).

Toda la configuración llega por variables de entorno inyectadas desde
Google Secret Manager en despliegue (PRD §10): nunca hay secretos en el
repositorio.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "dev"
    api_port: int = 8000

    # Base de datos PostgreSQL de Supabase (PRD §4)
    database_url: str = ""

    # Supabase Auth — verificación de JWT (PRD §9)
    supabase_url: str = ""
    supabase_jwt_secret: str = ""

    # Cola Celery / Redis (PRD §4)
    redis_url: str = "redis://localhost:6379/0"

    # Gmail API / Pub/Sub (PRD §Épica 2)
    google_pubsub_verification_token: str = ""
    pubsub_topic: str = "gmail-notifications"
    pubsub_subscription: str = "gmail-notifications-sub"

    # Motor de IA JEV (PRD §4)
    jev_api_key: str = ""
    jev_base_url: str = ""

    # Cifrado AES-256-GCM del google_refresh_token (PRD §F1.3)
    token_encryption_key: str = ""

    # Monitoreo (PRD §4)
    sentry_dsn: str = ""

    @property
    def is_prod(self) -> bool:
        return self.env == "prod"


@lru_cache
def get_settings() -> Settings:
    return Settings()
