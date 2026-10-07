"""Agregador de routers por dominio (monolito modular — PRD §5.2)."""

from fastapi import APIRouter

from app.billing.router import router as billing_router
from app.categories.router import router as categories_router
from app.dashboard.router import router as dashboard_router
from app.goals.router import router as goals_router
from app.integrations.gmail.router import router as gmail_router
from app.sync.router import router as sync_router
from app.transactions.router import router as transactions_router
from app.users.router import router as users_router

api_router = APIRouter()
api_router.include_router(users_router)  # POST /auth/session, /users/me
api_router.include_router(gmail_router)  # POST /webhooks/gmail
api_router.include_router(categories_router)
api_router.include_router(transactions_router)
api_router.include_router(dashboard_router)
api_router.include_router(goals_router)
api_router.include_router(sync_router)
api_router.include_router(billing_router)  # preparación SaaS (F4)
