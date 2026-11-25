import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.finance import FinancialAccount, FinancialTransfer


class TransferRepository:
    """Repository for FinancialTransfer records."""

    def create(self, db: Session, transfer: FinancialTransfer) -> FinancialTransfer:
        db.add(transfer)
        db.flush()
        return transfer

    def get_by_id(
        self, db: Session, transfer_id: uuid.UUID, user_id: uuid.UUID
    ) -> FinancialTransfer | None:
        stmt = (
            select(FinancialTransfer)
            .options(
                joinedload(FinancialTransfer.source_account),
                joinedload(FinancialTransfer.destination_account),
            )
            .where(
                FinancialTransfer.id == transfer_id,
                FinancialTransfer.user_id == user_id,
                FinancialTransfer.source_account.has(FinancialAccount.status != "disconnected"),
                FinancialTransfer.destination_account.has(
                    FinancialAccount.status != "disconnected"
                ),
            )
        )
        return db.execute(stmt).scalar_one_or_none()

    def list_by_user(
        self, db: Session, user_id: uuid.UUID, limit: int = 50
    ) -> list[FinancialTransfer]:
        stmt = (
            select(FinancialTransfer)
            .options(
                joinedload(FinancialTransfer.source_account),
                joinedload(FinancialTransfer.destination_account),
            )
            .where(
                FinancialTransfer.user_id == user_id,
                FinancialTransfer.source_account.has(FinancialAccount.status != "disconnected"),
                FinancialTransfer.destination_account.has(
                    FinancialAccount.status != "disconnected"
                ),
            )
            .order_by(FinancialTransfer.transfer_date.desc(), FinancialTransfer.created_at.desc())
            .limit(limit)
        )
        return list(db.execute(stmt).scalars().all())

    def update(self, db: Session, transfer: FinancialTransfer) -> FinancialTransfer:
        db.add(transfer)
        db.flush()
        return transfer
