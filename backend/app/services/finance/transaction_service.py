import datetime as dt
import math
import uuid
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.finance import FinancialTransaction
from app.models.user import User
from app.repositories.finance.account_repository import AccountRepository
from app.repositories.finance.category_repository import CategoryRepository
from app.repositories.finance.transaction_repository import TransactionRepository
from app.schemas.finance.transaction import (
    TransactionCreateRequest,
    TransactionListResponse,
    TransactionResponse,
    TransactionUpdateRequest,
)
from app.services.finance.ledger_service import LedgerService


class TransactionService:
    """Service for managing financial transactions with strict double-entry ledger synchronization."""

    def __init__(self):
        self.transaction_repo = TransactionRepository()
        self.account_repo = AccountRepository()
        self.category_repo = CategoryRepository()
        self.ledger_service = LedgerService()

    def _to_response(self, tx: FinancialTransaction) -> TransactionResponse:
        return TransactionResponse(
            id=tx.id,
            user_id=tx.user_id,
            account_id=tx.account_id,
            account_name=tx.account.name if tx.account else None,
            transaction_type=tx.transaction_type,
            amount=tx.amount,
            currency=tx.currency,
            category_id=tx.category_id,
            category_name=tx.category.name if tx.category else None,
            category_icon=tx.category.icon if tx.category else None,
            category_color=tx.category.color if tx.category else None,
            description=tx.description,
            merchant_payee=tx.merchant_payee,
            transaction_date=tx.transaction_date,
            notes=tx.notes,
            source=tx.source,
            external_reference=tx.external_reference,
            transfer_id=tx.transfer_id,
            created_at=tx.created_at,
            updated_at=tx.updated_at,
        )

    def create_transaction(
        self,
        db: Session,
        user: User,
        req: TransactionCreateRequest,
        source: str = "manual",
        external_reference: str | None = None,
        commit: bool = True,
    ) -> TransactionResponse:
        # Verify account ownership and active status
        account = self.account_repo.get_by_id(db, req.account_id, user.id)
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Financial account not found.",
            )
        if account.status != "active":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot add transactions to an archived account.",
            )

        # Prevent asset account balance from going negative on expenses
        if (
            source == "manual"
            and req.transaction_type == "expense"
            and account.account_type != "credit_card"
            and req.amount > account.current_balance
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Insufficient balance in '{account.name}'. "
                    f"Available balance is ₹{account.current_balance:,.2f}, "
                    f"cannot record expense of ₹{req.amount:,.2f}."
                ),
            )

        # Verify category if provided
        if req.category_id:
            category = self.category_repo.get_by_id(db, req.category_id, user.id)
            if not category:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Specified category was not found.",
                )

        try:
            tx = FinancialTransaction(
                user_id=user.id,
                account_id=account.id,
                transaction_type=req.transaction_type,
                amount=req.amount,
                currency=req.currency.upper(),
                category_id=req.category_id,
                description=req.description.strip(),
                merchant_payee=req.merchant_payee.strip() if req.merchant_payee else None,
                transaction_date=req.transaction_date,
                notes=req.notes.strip() if req.notes else None,
                source=source,
                external_reference=external_reference,
            )
            self.transaction_repo.create(db, tx)

            # Post balanced double-entry ledger journal
            self.ledger_service.post_transaction(
                db=db,
                user_id=user.id,
                transaction_id=tx.id,
                account_id=account.id,
                account_type=account.account_type,
                transaction_type=tx.transaction_type,
                amount=tx.amount,
                entry_date=tx.transaction_date,
                description=tx.description,
                currency=tx.currency,
            )

            if commit:
                db.commit()
            db.refresh(tx)
            return self._to_response(tx)
        except Exception:
            if commit:
                db.rollback()
            raise

    def get_transaction(
        self, db: Session, user: User, transaction_id: uuid.UUID
    ) -> TransactionResponse:
        tx = self.transaction_repo.get_by_id(db, transaction_id, user.id)
        if not tx:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transaction not found.",
            )
        return self._to_response(tx)

    def list_transactions(
        self,
        db: Session,
        user: User,
        account_id: uuid.UUID | None = None,
        transaction_type: str | None = None,
        category_id: uuid.UUID | None = None,
        source: str | None = None,
        start_date: dt.date | None = None,
        end_date: dt.date | None = None,
        search: str | None = None,
        sort_by: str = "date_desc",
        page: int = 1,
        page_size: int = 20,
    ) -> TransactionListResponse:
        items, total = self.transaction_repo.list_transactions(
            db=db,
            user_id=user.id,
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
        total_pages = math.ceil(total / page_size) if total > 0 else 1
        return TransactionListResponse(
            items=[self._to_response(tx) for tx in items],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    def update_transaction(
        self,
        db: Session,
        user: User,
        transaction_id: uuid.UUID,
        req: TransactionUpdateRequest,
    ) -> TransactionResponse:
        tx = self.transaction_repo.get_by_id(db, transaction_id, user.id)
        if not tx:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transaction not found.",
            )
        if tx.transfer_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Transactions linked to transfers cannot be directly updated. Reverse the transfer instead.",
            )

        try:
            amount_changed = req.amount is not None and req.amount != tx.amount
            date_changed = (
                req.transaction_date is not None and req.transaction_date != tx.transaction_date
            )

            if amount_changed or date_changed:
                # Reverse existing journal
                self.ledger_service.reverse_transaction_journal(
                    db=db,
                    transaction_id=tx.id,
                    account_id=tx.account_id,
                    account_type=tx.account.account_type,
                )

                if req.amount is not None:
                    tx.amount = req.amount
                if req.transaction_date is not None:
                    tx.transaction_date = req.transaction_date

                # Post updated journal
                self.ledger_service.post_transaction(
                    db=db,
                    user_id=user.id,
                    transaction_id=tx.id,
                    account_id=tx.account_id,
                    account_type=tx.account.account_type,
                    transaction_type=tx.transaction_type,
                    amount=tx.amount,
                    entry_date=tx.transaction_date,
                    description=req.description.strip() if req.description else tx.description,
                    currency=tx.currency,
                )

            if req.category_id is not None:
                if req.category_id:
                    cat = self.category_repo.get_by_id(db, req.category_id, user.id)
                    if not cat:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Specified category not found.",
                        )
                tx.category_id = req.category_id

            if req.description is not None:
                tx.description = req.description.strip()
            if req.merchant_payee is not None:
                tx.merchant_payee = req.merchant_payee.strip() if req.merchant_payee else None
            if req.notes is not None:
                tx.notes = req.notes.strip() if req.notes else None

            self.transaction_repo.update(db, tx)
            if (amount_changed or date_changed) and tx.account.account_type != "credit_card":
                db.refresh(tx.account)
                if tx.account.current_balance < Decimal("0.00"):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            f"Insufficient balance: updating this transaction would reduce "
                            f"'{tx.account.name}' balance below ₹0.00."
                        ),
                    )
            db.commit()
            db.refresh(tx)
            return self._to_response(tx)
        except Exception:
            db.rollback()
            raise

    def delete_transaction(self, db: Session, user: User, transaction_id: uuid.UUID) -> None:
        tx = self.transaction_repo.get_by_id(db, transaction_id, user.id)
        if not tx:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transaction not found.",
            )
        if tx.transfer_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Transactions linked to transfers cannot be deleted individually. Reverse the transfer instead.",
            )

        try:
            account_ref = tx.account
            # Reverse journal in ledger and recalculate balance
            self.ledger_service.reverse_transaction_journal(
                db=db,
                transaction_id=tx.id,
                account_id=tx.account_id,
                account_type=tx.account.account_type,
            )

            if account_ref.account_type != "credit_card":
                db.refresh(account_ref)
                if account_ref.current_balance < Decimal("0.00"):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            f"Cannot delete this income transaction because '{account_ref.name}' "
                            f"balance would become negative."
                        ),
                    )

            self.transaction_repo.delete(db, tx)
            db.commit()
        except Exception:
            db.rollback()
            raise
