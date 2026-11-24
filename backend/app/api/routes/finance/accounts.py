import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, verify_csrf
from app.models.user import User
from app.schemas.finance.account import (
    AccountCreateRequest,
    AccountOpeningBalanceUpdateRequest,
    AccountResponse,
    AccountSummaryResponse,
    AccountUpdateRequest,
)
from app.services.finance.account_service import AccountService

router = APIRouter(prefix="/finance/accounts", tags=["Financial Accounts"])
account_service = AccountService()


@router.post("", response_model=AccountResponse, summary="Create a financial account")
def create_account(
    req: AccountCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    """Creates a new financial account (Savings, Current, Cash, Credit Card, Wallet) with initial balance."""
    return account_service.create_account(db, current_user, req)


@router.get("", response_model=list[AccountResponse], summary="List financial accounts")
def list_accounts(
    include_archived: bool = Query(False, description="Whether to include archived accounts"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns all financial accounts owned by the authenticated user."""
    return account_service.list_accounts(db, current_user, include_archived=include_archived)


@router.get("/summary", response_model=AccountSummaryResponse, summary="Get accounts summary")
def get_accounts_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns aggregate summary metrics across user accounts (assets, liabilities, net position)."""
    return account_service.get_summary(db, current_user)


@router.get("/{account_id}", response_model=AccountResponse, summary="Get account details")
def get_account(
    account_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieves single financial account details."""
    return account_service.get_account(db, current_user, account_id)


@router.patch("/{account_id}", response_model=AccountResponse, summary="Update account metadata")
def update_account(
    account_id: uuid.UUID,
    req: AccountUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    """Updates permitted account fields (name, type, institution, masked identifier)."""
    return account_service.update_account(db, current_user, account_id, req)


@router.patch(
    "/{account_id}/opening-balance",
    response_model=AccountResponse,
    summary="Correct opening balance",
)
def update_opening_balance(
    account_id: uuid.UUID,
    req: AccountOpeningBalanceUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    """Corrects opening balance with audit trail preservation and ledger recalculation."""
    return account_service.update_opening_balance(db, current_user, account_id, req)


@router.post("/{account_id}/archive", response_model=AccountResponse, summary="Archive an account")
def archive_account(
    account_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    """Safely archives an account, preserving all historical transactions and ledger postings."""
    return account_service.archive_account(db, current_user, account_id)


@router.post(
    "/{account_id}/restore", response_model=AccountResponse, summary="Restore an archived account"
)
def restore_account(
    account_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    """Restores an archived account back to active status."""
    return account_service.restore_account(db, current_user, account_id)
