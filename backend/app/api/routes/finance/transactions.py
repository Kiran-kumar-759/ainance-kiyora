import datetime as dt
import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, verify_csrf
from app.models.user import User
from app.schemas.finance.transaction import (
    TransactionCreateRequest,
    TransactionListResponse,
    TransactionResponse,
    TransactionUpdateRequest,
)
from app.services.finance.transaction_service import TransactionService

router = APIRouter(prefix="/finance/transactions", tags=["Financial Transactions"])
transaction_service = TransactionService()


@router.post("", response_model=TransactionResponse, summary="Record a financial transaction")
def create_transaction(
    req: TransactionCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    """Records an income or expense transaction and atomically posts balanced ledger entries."""
    return transaction_service.create_transaction(db, current_user, req)


@router.get("", response_model=TransactionListResponse, summary="List transactions with filters")
def list_transactions(
    account_id: uuid.UUID | None = Query(None, description="Filter by account"),
    transaction_type: str | None = Query(None, description="income, expense, or transfer"),
    category_id: uuid.UUID | None = Query(None, description="Filter by category"),
    source: str | None = Query(None, description="manual or demo_bank"),
    start_date: dt.date | None = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: dt.date | None = Query(None, description="End date (YYYY-MM-DD)"),
    search: str | None = Query(None, description="Search description, payee, notes"),
    sort_by: str = Query("date_desc", description="date_desc, date_asc, amount_desc, amount_asc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns paginated financial transactions matching criteria for the authenticated user."""
    return transaction_service.list_transactions(
        db=db,
        user=current_user,
        account_id=account_id,
        transaction_type=transaction_type,
        category_id=category_id,
        source=source,
        start_date=start_date,
        end_date=end_date,
        search=search,
        sort_by=sort_by,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{transaction_id}", response_model=TransactionResponse, summary="Get transaction details"
)
def get_transaction(
    transaction_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieves single transaction details."""
    return transaction_service.get_transaction(db, current_user, transaction_id)


@router.patch("/{transaction_id}", response_model=TransactionResponse, summary="Update transaction")
def update_transaction(
    transaction_id: uuid.UUID,
    req: TransactionUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    """Updates permitted transaction fields and syncs ledger postings if amount/date changed."""
    return transaction_service.update_transaction(db, current_user, transaction_id, req)


@router.delete(
    "/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete transaction"
)
def delete_transaction(
    transaction_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    """Safely deletes a transaction, reversing its ledger entries and recalculating account balances."""
    transaction_service.delete_transaction(db, current_user, transaction_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
