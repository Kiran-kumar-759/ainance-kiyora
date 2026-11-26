import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, verify_csrf
from app.core.rate_limit import rate_limiter
from app.models.user import User
from app.schemas.integrations import (
    IntegrationConnectionSummary,
    IntegrationDisconnectResponse,
    IntegrationItemResponse,
    IntegrationsOverviewResponse,
    IntegrationTestResponse,
)
from app.services.integrations.integration_service import IntegrationService

router = APIRouter(prefix="/integrations", tags=["Integrations Center"])
integration_service = IntegrationService()


@router.get("/overview", response_model=IntegrationsOverviewResponse)
def get_integrations_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns real configured/connected/unavailable counts and provider inventory."""
    return integration_service.get_overview(db, current_user)


@router.get("/providers", response_model=list[IntegrationItemResponse])
def list_integration_providers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return integration_service.list_providers(db, current_user)


@router.get("/providers/{provider_id}", response_model=IntegrationItemResponse)
def get_integration_provider(
    provider_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return integration_service.get_provider(db, current_user, provider_id)


@router.post("/providers/{provider_id}/test", response_model=IntegrationTestResponse)
def test_integration_provider(
    provider_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    """Executes a bounded, rate-limited non-mutating health check for a specific provider."""
    if not rate_limiter.is_allowed(
        f"integration_test:{current_user.id}", max_requests=10, window_seconds=60
    ):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many provider connection tests. Please wait a minute and retry.",
        )
    return integration_service.test_provider(db, current_user, provider_id)


@router.get("/connections", response_model=list[IntegrationConnectionSummary])
def list_integration_connections(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return integration_service.list_connections(db, current_user)


@router.get("/connections/{connection_id}", response_model=IntegrationConnectionSummary)
def get_integration_connection(
    connection_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return integration_service.get_connection(db, current_user, connection_id)


@router.post("/connections/{connection_id}/disconnect", response_model=IntegrationDisconnectResponse)
def disconnect_integration_connection(
    connection_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    return integration_service.disconnect_connection(db, current_user, connection_id)
