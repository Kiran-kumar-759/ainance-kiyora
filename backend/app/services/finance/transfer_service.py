import datetime as dt
import uuid
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.finance import FinancialTransaction, FinancialTransfer
from app.models.user import User
from app.repositories.finance.account_repository import AccountRepository
from app.repositories.finance.transaction_repository import TransactionRepository
from app.repositories.finance.transfer_repository import TransferRepository
from app.schemas.finance.transfer import (
    TransferCreateRequest,
    TransferResponse,
    TransferReverseRequest,
)
from app.services.finance.ledger_service import LedgerService


class TransferService:
    """Service managing atomic fund transfers between user accounts and transfer reversals."""

    def __init__(self):
        self.transfer_repo = TransferRepository()
        self.account_repo = AccountRepository()
        self.transaction_repo = TransactionRepository()
        self.ledger_service = LedgerService()

    def _to_response(self, tr: FinancialTransfer) -> TransferResponse:
        return TransferResponse(
            id=tr.id,
            user_id=tr.user_id,
            source_account_id=tr.source_account_id,
            source_account_name=tr.source_account.name if tr.source_account else None,
            destination_account_id=tr.destination_account_id,
            destination_account_name=tr.destination_account.name
            if tr.destination_account
            else None,
            amount=tr.amount,
            currency=tr.currency,
            transfer_date=tr.transfer_date,
            description=tr.description,
            status=tr.status,
            reversal_reason=tr.reversal_reason,
            reversed_at=tr.reversed_at,
            created_at=tr.created_at,
        )

    def execute_transfer(
        self, db: Session, user: User, req: TransferCreateRequest
    ) -> TransferResponse:
        # Validation 1: Source and destination cannot be identical
        if req.source_account_id == req.destination_account_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Source and destination accounts cannot be the same.",
            )

        # Validation 2: Both accounts belong to authenticated user
        source_acc = self.account_repo.get_by_id(db, req.source_account_id, user.id)
        if not source_acc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Source account not found.",
            )
        dest_acc = self.account_repo.get_by_id(db, req.destination_account_id, user.id)
        if not dest_acc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Destination account not found.",
            )

        # Validation 3: Both accounts must be active
        if source_acc.status != "active":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Source account is archived.",
            )
        if dest_acc.status != "active":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Destination account is archived.",
            )

        # Validation 4: Currency compatibility
        if source_acc.currency != dest_acc.currency:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Currency mismatch: source is {source_acc.currency}, destination is {dest_acc.currency}. Cross-currency transfers require exchange rate conversion.",
            )

        # Validation 5: Asset source account must have sufficient balance
        if source_acc.account_type != "credit_card" and req.amount > source_acc.current_balance:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Insufficient balance in '{source_acc.name}'. "
                    f"Available balance is ₹{source_acc.current_balance:,.2f}, "
                    f"cannot transfer ₹{req.amount:,.2f}."
                ),
            )

        transfer_desc = (
            req.description.strip()
            if req.description
            else f"Transfer from {source_acc.name} to {dest_acc.name}"
        )

        try:
            transfer = FinancialTransfer(
                user_id=user.id,
                source_account_id=source_acc.id,
                destination_account_id=dest_acc.id,
                amount=req.amount,
                currency=source_acc.currency,
                transfer_date=req.transfer_date,
                description=transfer_desc,
                status="completed",
            )
            self.transfer_repo.create(db, transfer)

            # Create two paired transaction ledger representations for user visibility
            source_tx = FinancialTransaction(
                user_id=user.id,
                account_id=source_acc.id,
                transaction_type="transfer",
                amount=req.amount,
                currency=source_acc.currency,
                description=f"Transfer to {dest_acc.name}: {transfer_desc}",
                transaction_date=req.transfer_date,
                source="manual",
                transfer_id=transfer.id,
            )
            dest_tx = FinancialTransaction(
                user_id=user.id,
                account_id=dest_acc.id,
                transaction_type="transfer",
                amount=req.amount,
                currency=dest_acc.currency,
                description=f"Transfer from {source_acc.name}: {transfer_desc}",
                transaction_date=req.transfer_date,
                source="manual",
                transfer_id=transfer.id,
            )
            self.transaction_repo.create(db, source_tx)
            self.transaction_repo.create(db, dest_tx)

            transfer.source_transaction_id = source_tx.id
            transfer.destination_transaction_id = dest_tx.id
            self.transfer_repo.update(db, transfer)

            # Post atomic balanced ledger entry (Credit source, Debit destination)
            self.ledger_service.post_transfer(
                db=db,
                user_id=user.id,
                transfer_id=transfer.id,
                source_account_id=source_acc.id,
                source_account_type=source_acc.account_type,
                dest_account_id=dest_acc.id,
                dest_account_type=dest_acc.account_type,
                amount=req.amount,
                entry_date=req.transfer_date,
                description=transfer_desc,
                currency=source_acc.currency,
            )

            db.commit()
            db.refresh(transfer)
            return self.get_transfer(db, user, transfer.id)
        except Exception:
            db.rollback()
            raise

    def get_transfer(self, db: Session, user: User, transfer_id: uuid.UUID) -> TransferResponse:
        tr = self.transfer_repo.get_by_id(db, transfer_id, user.id)
        if not tr:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transfer not found.",
            )
        return self._to_response(tr)

    def list_transfers(self, db: Session, user: User, limit: int = 50) -> list[TransferResponse]:
        transfers = self.transfer_repo.list_by_user(db, user.id, limit=limit)
        return [self._to_response(tr) for tr in transfers]

    def reverse_transfer(
        self,
        db: Session,
        user: User,
        transfer_id: uuid.UUID,
        req: TransferReverseRequest,
    ) -> TransferResponse:
        tr = self.transfer_repo.get_by_id(db, transfer_id, user.id)
        if not tr:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transfer not found.",
            )
        if tr.status == "reversed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This transfer has already been reversed.",
            )

        try:
            # Reverse the ledger journal and recalculate both balances
            self.ledger_service.reverse_transfer_journal(
                db=db,
                transfer_id=tr.id,
                source_account_id=tr.source_account_id,
                source_account_type=tr.source_account.account_type,
                dest_account_id=tr.destination_account_id,
                dest_account_type=tr.destination_account.account_type,
            )

            db.refresh(tr.source_account)
            db.refresh(tr.destination_account)
            for acc in (tr.source_account, tr.destination_account):
                if acc.account_type != "credit_card" and acc.current_balance < Decimal("0.00"):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            f"Cannot reverse transfer because '{acc.name}' has insufficient "
                            f"balance to cover the reversal."
                        ),
                    )

            tr.status = "reversed"
            tr.reversal_reason = req.reason.strip()
            tr.reversed_at = dt.datetime.now(dt.UTC)
            self.transfer_repo.update(db, tr)

            db.commit()
            db.refresh(tr)
            return self.get_transfer(db, user, tr.id)
        except Exception:
            db.rollback()
            raise
