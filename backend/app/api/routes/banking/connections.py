import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, verify_csrf
from app.models.user import User
from app.schemas.finance.account import AccountResponse
from app.schemas.finance.banking import (
    BankingAccountImportRequest,
    BankingConnectionResponse,
    BankingConsentRequest,
    BankingProviderInfo,
    BankingSyncResponse,
    BankingSyncRunResponse,
    DiscoveredAccountInfo,
)
from app.services.banking.banking_service import BankingService

router = APIRouter(prefix="/banking", tags=["Simulated Banking Connections"])
banking_service = BankingService()


@router.get(
    "/providers",
    response_model=list[BankingProviderInfo],
    summary="List available simulated providers",
)
def list_providers():
    """Lists available simulated demo banking institutions with disclaimers and capabilities."""
    return banking_service.list_providers()


@router.post(
    "/connections/demo",
    response_model=BankingConnectionResponse,
    summary="Connect simulated demo bank",
)
def create_demo_connection(
    req: BankingConsentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    """Initializes a simulated demo banking connection following explicit user consent."""
    return banking_service.create_demo_connection(db, current_user, req)


@router.get(
    "/connections",
    response_model=list[BankingConnectionResponse],
    summary="List user banking connections",
)
def list_user_connections(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns all banking connections established by the authenticated user."""
    return banking_service.list_user_connections(db, current_user)


@router.get(
    "/connections/{connection_id}",
    response_model=BankingConnectionResponse,
    summary="Get connection details",
)
def get_connection(
    connection_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieves banking connection details."""
    return banking_service.get_connection(db, current_user, connection_id)


@router.get(
    "/connections/{connection_id}/accounts",
    response_model=list[DiscoveredAccountInfo],
    summary="Discover accounts from provider",
)
def discover_accounts(
    connection_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Discovers available accounts from the connected simulated banking provider."""
    return banking_service.discover_accounts(db, current_user, connection_id)


@router.post(
    "/connections/{connection_id}/accounts/import",
    response_model=list[AccountResponse],
    summary="Import selected discovered accounts",
)
def import_accounts(
    connection_id: uuid.UUID,
    req: BankingAccountImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    """Imports selected discovered bank accounts into user's financial accounts."""
    return banking_service.import_accounts(db, current_user, connection_id, req)


@router.post(
    "/connections/{connection_id}/sync",
    response_model=BankingSyncResponse,
    summary="Synchronize demo transactions",
)
def sync_connection(
    connection_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    """Synchronizes transactions idempotently from the connected provider."""
    return banking_service.sync_connection(db, current_user, connection_id)


@router.get(
    "/connections/{connection_id}/sync-runs",
    response_model=list[BankingSyncRunResponse],
    summary="List synchronization history for a connection",
)
def list_sync_runs(
    connection_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns audit history of synchronization runs for a banking connection."""
    return banking_service.list_sync_runs(db, current_user, connection_id)


@router.post(
    "/connections/{connection_id}/disconnect",
    response_model=BankingConnectionResponse,
    summary="Disconnect banking connection",
)
def disconnect_connection(
    connection_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    """Disconnects the simulated provider connection. Existing imported data is preserved."""
    return banking_service.disconnect_connection(db, current_user, connection_id)
