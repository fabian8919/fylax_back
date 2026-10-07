"""Sesión de base de datos: PostgreSQL gestionado en Supabase.

Transacciones ACID obligatorias para dinero (PRD §4). La Row Level
Security de Supabase actúa como segunda línea de defensa (PRD §10), pero
el backend SIEMPRE filtra por user_id además (defensa en profundidad).
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependencia FastAPI: una sesión por petición."""
    async with SessionLocal() as session:
        yield session
