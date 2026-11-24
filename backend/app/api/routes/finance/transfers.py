import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, verify_csrf
from app.models.user import User
from app.schemas.finance.transfer import (
    TransferCreateRequest,
    TransferResponse,
    TransferReverseRequest,
)
from app.services.finance.transfer_service import TransferService

router = APIRouter(prefix="/finance/transfers", tags=["Financial Transfers"])
transfer_service = TransferService()


@router.post("", response_model=TransferResponse, summary="Execute fund transfer between accounts")
def execute_transfer(
    req: TransferCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    """Executes an atomic money transfer between two user accounts with dual ledger postings."""
    return transfer_service.execute_transfer(db, current_user, req)


@router.get("", response_model=list[TransferResponse], summary="List transfer history")
def list_transfers(
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns recent money transfers executed by the authenticated user."""
    return transfer_service.list_transfers(db, current_user, limit=limit)


@router.get("/{transfer_id}", response_model=TransferResponse, summary="Get transfer details")
def get_transfer(
    transfer_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieves single transfer details."""
    return transfer_service.get_transfer(db, current_user, transfer_id)


@router.post(
    "/{transfer_id}/reverse", response_model=TransferResponse, summary="Reverse a transfer"
)
def reverse_transfer(
    transfer_id: uuid.UUID,
    req: TransferReverseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    """Reverses a transfer atomically and recalculates source and destination account balances."""
    return transfer_service.reverse_transfer(db, current_user, transfer_id, req)
