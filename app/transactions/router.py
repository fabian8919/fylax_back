"""Dominio transactions (PRD §9).

GET    /transactions        lista paginada (filtros fecha/categoría/fuente)
POST   /transactions        creación manual (F3.3)
PATCH  /transactions/{id}   edición de monto/categoría/comercio (F3.3)
DELETE /transactions/{id}

Idempotencia: UNIQUE (user_id, source_ref_id) — PRD §F2.6. Las
transacciones automáticas se insertan desde el worker de ingesta, nunca
desde el hilo web (ADR Web/Workers — PRD §5.2).
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.pagination import PageParams, pagination_params
from app.core.exceptions import DuplicateTransactionError
from app.core.security import CurrentUser, get_current_user
from app.db.models import Transaction, TransactionSource
from app.db.session import get_db
from app.transactions.schemas import (
    TransactionCreate,
    TransactionResponse,
    TransactionUpdate,
)

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("", response_model=list[TransactionResponse])
async def list_transactions(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    page: PageParams = Depends(pagination_params),
    category_id: uuid.UUID | None = None,
    source: TransactionSource | None = None,
    date_from: datetime | None = Query(None, alias="from"),
    date_to: datetime | None = Query(None, alias="to"),
) -> list[Transaction]:
    """Lista paginada del usuario autenticado, SIEMPRE filtrada por user_id."""
    stmt = (
        select(Transaction)
        .where(Transaction.user_id == current_user.id)
        .order_by(Transaction.date.desc())
        .offset(page.offset)
        .limit(page.page_size)
    )
    if category_id:
        stmt = stmt.where(Transaction.category_id == category_id)
    if source:
        stmt = stmt.where(Transaction.source == source.value)
    if date_from:
        stmt = stmt.where(Transaction.date >= date_from)
    if date_to:
        stmt = stmt.where(Transaction.date <= date_to)

    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
async def create_transaction(
    body: TransactionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> Transaction:
    tx = Transaction(
        user_id=current_user.id,
        category_id=body.category_id,
        amount=body.amount,
        currency=body.currency,
        date=body.date,
        merchant_clean=body.merchant_clean.strip(),
        source=TransactionSource.manual.value,
        source_ref_id=None,  # la idempotencia no aplica a manuales
    )
    db.add(tx)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise DuplicateTransactionError from exc
    await db.refresh(tx)
    return tx


@router.patch("/{transaction_id}", response_model=TransactionResponse)
async def update_transaction(
    transaction_id: uuid.UUID,
    body: TransactionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> Transaction:
    tx = await _get_own_transaction(db, current_user.id, transaction_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(tx, field, value)
    await db.commit()
    await db.refresh(tx)
    return tx


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(
    transaction_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> None:
    await _get_own_transaction(db, current_user.id, transaction_id)
    await db.execute(
        delete(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.user_id == current_user.id,
        )
    )
    await db.commit()


async def _get_own_transaction(
    db: AsyncSession, user_id: uuid.UUID, transaction_id: uuid.UUID
) -> Transaction:
    result = await db.execute(
        select(Transaction).where(
            Transaction.id == transaction_id, Transaction.user_id == user_id
        )
    )
    tx = result.scalar_one_or_none()
    if tx is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Transacción no encontrada")
    return tx
