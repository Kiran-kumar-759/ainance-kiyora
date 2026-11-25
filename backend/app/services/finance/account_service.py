import datetime as dt
import uuid
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.finance import FinancialAccount, LedgerJournal
from app.models.user import User
from app.repositories.finance.account_repository import AccountRepository
from app.schemas.finance.account import (
    AccountCreateRequest,
    AccountOpeningBalanceUpdateRequest,
    AccountResponse,
    AccountSummaryResponse,
    AccountUpdateRequest,
)
from app.services.finance.ledger_service import LedgerService


class AccountService:
    """Service managing financial accounts, opening balances, and balance integrity."""

    def __init__(self):
        self.account_repo = AccountRepository()
        self.ledger_service = LedgerService()

    def create_account(
        self,
        db: Session,
        user: User,
        req: AccountCreateRequest,
        source: str = "manual",
        commit: bool = True,
    ) -> AccountResponse:
        if source == "manual":
            existing = self.account_repo.get_active_by_name_and_type(
                db, user.id, req.name, req.account_type
            )
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"An active {req.account_type.replace('_', ' ')} account named '{req.name.strip()}' already exists.",
                )

        try:
            account = FinancialAccount(
                user_id=user.id,
                name=req.name.strip(),
                account_type=req.account_type,
                institution_name=req.institution_name.strip()
                if req.institution_name and req.institution_name.strip()
                else None,
                account_identifier=req.account_identifier.strip()
                if req.account_identifier and req.account_identifier.strip()
                else None,
                currency=req.currency.upper(),
                opening_balance=req.opening_balance,
                current_balance=Decimal("0.00"),
                status="active",
                source=source,
            )
            self.account_repo.create(db, account)

            # Post opening balance to ledger if > 0
            if req.opening_balance > Decimal("0.00"):
                self.ledger_service.post_opening_balance(
                    db=db,
                    user_id=user.id,
                    account_id=account.id,
                    account_type=account.account_type,
                    amount=req.opening_balance,
                    entry_date=dt.date.today(),
                    currency=account.currency,
                )
            else:
                self.ledger_service.recalculate_and_sync_account_balance(
                    db, account.id, account.account_type
                )

            if commit:
                db.commit()
            db.refresh(account)
            return AccountResponse.model_validate(account)
        except Exception:
            if commit:
                db.rollback()
            raise

    def list_accounts(
        self, db: Session, user: User, include_archived: bool = False
    ) -> list[AccountResponse]:
        accounts = self.account_repo.list_by_user(db, user.id, include_archived=include_archived)
        return [AccountResponse.model_validate(a) for a in accounts]

    def get_account(self, db: Session, user: User, account_id: uuid.UUID) -> AccountResponse:
        account = self.account_repo.get_by_id(db, account_id, user.id)
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Financial account not found.",
            )
        return AccountResponse.model_validate(account)

    def update_account(
        self,
        db: Session,
        user: User,
        account_id: uuid.UUID,
        req: AccountUpdateRequest,
    ) -> AccountResponse:
        account = self.account_repo.get_by_id(db, account_id, user.id)
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Financial account not found.",
            )
        try:
            if req.name is not None:
                account.name = req.name.strip()
            if req.account_type is not None:
                account.account_type = req.account_type
            if req.institution_name is not None:
                account.institution_name = (
                    req.institution_name.strip() if req.institution_name.strip() else None
                )
            if req.account_identifier is not None:
                account.account_identifier = (
                    req.account_identifier.strip() if req.account_identifier.strip() else None
                )

            self.account_repo.update(db, account)
            self.ledger_service.recalculate_and_sync_account_balance(
                db, account.id, account.account_type
            )
            db.commit()
            db.refresh(account)
            return AccountResponse.model_validate(account)
        except Exception:
            db.rollback()
            raise

    def update_opening_balance(
        self,
        db: Session,
        user: User,
        account_id: uuid.UUID,
        req: AccountOpeningBalanceUpdateRequest,
    ) -> AccountResponse:
        """Controlled operation to correct an opening balance with audit trail preservation."""
        account = self.account_repo.get_by_id(db, account_id, user.id)
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Financial account not found.",
            )

        try:
            # Find existing opening balance journal if any, and reverse it
            stmt = select(LedgerJournal).where(
                LedgerJournal.user_id == user.id,
                LedgerJournal.journal_type == "opening_balance",
                LedgerJournal.reference == f"OB-{account.id.hex[:8]}",
                LedgerJournal.is_reversed.is_(False),
            )
            existing_journal = db.execute(stmt).scalar_one_or_none()
            if existing_journal:
                existing_journal.is_reversed = True
                db.add(existing_journal)
                db.flush()

            account.opening_balance = req.opening_balance
            self.account_repo.update(db, account)

            # Post new opening balance
            if req.opening_balance > Decimal("0.00"):
                self.ledger_service.post_opening_balance(
                    db=db,
                    user_id=user.id,
                    account_id=account.id,
                    account_type=account.account_type,
                    amount=req.opening_balance,
                    entry_date=dt.date.today(),
                    currency=account.currency,
                )
            else:
                self.ledger_service.recalculate_and_sync_account_balance(
                    db, account.id, account.account_type
                )

            db.refresh(account)
            if account.account_type not in {"credit_card", "loan_liability"} and account.current_balance < Decimal("0.00"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Cannot reduce opening balance of '{account.name}' because resulting "
                        f"balance would be negative (₹{account.current_balance:,.2f})."
                    ),
                )

            db.commit()
            db.refresh(account)
            return AccountResponse.model_validate(account)
        except Exception:
            db.rollback()
            raise

    def archive_account(self, db: Session, user: User, account_id: uuid.UUID) -> AccountResponse:
        account = self.account_repo.get_by_id(db, account_id, user.id)
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Financial account not found.",
            )
        try:
            account.status = "archived"
            self.account_repo.update(db, account)
            db.commit()
            db.refresh(account)
            return AccountResponse.model_validate(account)
        except Exception:
            db.rollback()
            raise

    def restore_account(self, db: Session, user: User, account_id: uuid.UUID) -> AccountResponse:
        account = self.account_repo.get_by_id(db, account_id, user.id)
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Financial account not found.",
            )
        try:
            account.status = "active"
            self.account_repo.update(db, account)
            db.commit()
            db.refresh(account)
            return AccountResponse.model_validate(account)
        except Exception:
            db.rollback()
            raise

    def get_summary(self, db: Session, user: User) -> AccountSummaryResponse:
        accounts = self.account_repo.list_by_user(db, user.id, include_archived=True)
        total_accounts = len(accounts)
        active_accounts = sum(1 for a in accounts if a.status == "active")

        total_assets = Decimal("0.00")
        total_credit_liabilities = Decimal("0.00")

        for a in accounts:
            if a.status != "active":
                continue
            if a.account_type in {"credit_card", "loan_liability"}:
                total_credit_liabilities += a.current_balance
            else:
                total_assets += a.current_balance

        net_position = total_assets - total_credit_liabilities

        return AccountSummaryResponse(
            total_accounts=total_accounts,
            active_accounts=active_accounts,
            total_assets=total_assets,
            total_credit_liabilities=total_credit_liabilities,
            net_position=net_position,
        )
