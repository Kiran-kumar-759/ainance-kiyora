from fastapi import APIRouter

from app.api.routes import (
    analytics,
    assistant,
    auth,
    bills,
    documents,
    email,
    forecasting,
    imports,
    integrations,
    intelligence,
    loans,
    notifications,
    onboarding,
    reports,
    subscriptions,
    system,
    users,
)
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
api_router.include_router(imports.router)
api_router.include_router(analytics.router)
api_router.include_router(reports.router)
api_router.include_router(bills.router)
api_router.include_router(notifications.router)
api_router.include_router(subscriptions.router)
api_router.include_router(loans.router)
api_router.include_router(documents.router)
api_router.include_router(email.router)
api_router.include_router(intelligence.router)
api_router.include_router(forecasting.router)
api_router.include_router(assistant.router)
api_router.include_router(integrations.router)
