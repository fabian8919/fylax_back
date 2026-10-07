"""Excepciones de dominio.

DTOs estrictos con Pydantic en la frontera (PRD §5.2); dentro del
servicio se usan estas excepciones y los routers las traducen a HTTP.
"""


class DomainError(Exception):
    """Base de errores de dominio."""


class DuplicateTransactionError(DomainError):
    """Violación de idempotencia UNIQUE (user_id, source_ref_id)."""


class GmailScopeRevokedError(DomainError):
    """El usuario revocó el permiso gmail.readonly."""


class TierLimitExceededError(DomainError):
    """El tier free superó su cupo mensual de correos (PRD §F4.1)."""


class EmailParseError(DomainError):
    """Ni el parser determinista ni JEV lograron extraer el gasto."""
