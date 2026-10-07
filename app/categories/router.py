"""Dominio categories: GET /categories (PRD §9).

Devuelve las categorías del sistema (user_id NULL) más las
personalizadas del usuario autenticado. La semilla base vive en
app.categories.seed (fuente única, compartida con la migración 0001).
"""

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.categories.seed import DEFAULT_CATEGORIES  # noqa: F401 — re-export
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
    """Catálogo del sistema + categorías personalizadas del usuario."""
    result = await db.execute(
        select(Category)
        .where(or_(Category.user_id.is_(None), Category.user_id == current_user.id))
        .order_by(Category.is_system_default.desc(), Category.name)
    )
    return list(result.scalars().all())
