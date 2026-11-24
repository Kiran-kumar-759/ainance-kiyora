import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.finance import FinancialAccount


class AccountRepository:
    """Repository for FinancialAccount persistence and querying with strict user isolation."""

    def create(self, db: Session, account: FinancialAccount) -> FinancialAccount:
        db.add(account)
        db.flush()
        return account

    def get_by_id(
        self, db: Session, account_id: uuid.UUID, user_id: uuid.UUID
    ) -> FinancialAccount | None:
        stmt = select(FinancialAccount).where(
            FinancialAccount.id == account_id,
            FinancialAccount.user_id == user_id,
        )
        return db.execute(stmt).scalar_one_or_none()

    def list_by_user(
        self, db: Session, user_id: uuid.UUID, include_archived: bool = False
    ) -> list[FinancialAccount]:
        stmt = select(FinancialAccount).where(FinancialAccount.user_id == user_id)
        if not include_archived:
            stmt = stmt.where(FinancialAccount.status == "active")
        stmt = stmt.order_by(FinancialAccount.created_at.asc())
        return list(db.execute(stmt).scalars().all())

    def update(self, db: Session, account: FinancialAccount) -> FinancialAccount:
        db.add(account)
        db.flush()
        return account

    def update_balance(self, db: Session, account_id: uuid.UUID, new_balance: Decimal) -> None:
        stmt = select(FinancialAccount).where(FinancialAccount.id == account_id)
        account = db.execute(stmt).scalar_one_or_none()
        if account:
            account.current_balance = new_balance
            db.add(account)
            db.flush()
