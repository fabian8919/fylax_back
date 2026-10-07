"""Dominio categories: GET /categories (PRD §9).

Devuelve las categorías del sistema (is_system_default) más las
personalizadas del usuario.
"""

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser, get_current_user
from app.db.models import Category
from app.db.session import get_db

router = APIRouter(prefix="/categories", tags=["categories"])


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    icon: str
    color: str
    type: str
    is_system_default: bool


@router.get("", response_model=list[CategoryResponse])
async def list_categories(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[Category]:
    # TODO(Fase 4): incluir categorías personalizadas del usuario
    # (user_id NULL = del sistema, o user_id = actual).
    result = await db.execute(select(Category).order_by(Category.name))
    return list(result.scalars().all())


# Semilla de categorías por defecto del sistema (PRD §8 — is_system_default).
DEFAULT_CATEGORIES: list[dict[str, str]] = [
    {"name": "Alimentación", "icon": "restaurant", "color": "#E67E22", "type": "expense"},
    {"name": "Domicilios", "icon": "delivery_dining", "color": "#D35400", "type": "expense"},
    {"name": "Transporte", "icon": "directions_car", "color": "#2980B9", "type": "expense"},
    {"name": "Servicios", "icon": "receipt", "color": "#8E44AD", "type": "expense"},
    {"name": "Vivienda", "icon": "home", "color": "#27AE60", "type": "expense"},
    {"name": "Salud", "icon": "medical_services", "color": "#C0392B", "type": "expense"},
    {"name": "Ocio", "icon": "sports_esports", "color": "#F39C12", "type": "expense"},
    {"name": "Compras", "icon": "shopping_bag", "color": "#16A085", "type": "expense"},
    {"name": "Ingresos", "icon": "payments", "color": "#1B7A43", "type": "income"},
]
