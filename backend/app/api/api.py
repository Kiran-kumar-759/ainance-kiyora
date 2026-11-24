from fastapi import APIRouter

from app.api.routes import auth, onboarding, system, users
from app.api.routes.banking import connections
from app.api.routes.finance import (
    accounts,
    categories,
    dashboard,
    transactions,
    transfers,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(onboarding.router)
api_router.include_router(system.router)

# Phase 2 Finance & Banking routes
api_router.include_router(accounts.router)
api_router.include_router(categories.router)
api_router.include_router(transactions.router)
api_router.include_router(transfers.router)
api_router.include_router(dashboard.router)
api_router.include_router(connections.router)
