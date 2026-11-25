import datetime as dt
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.finance import FinancialAccount, FinancialTransaction


class TransactionRepository:
    """Repository for FinancialTransaction persistence, multi-criteria filtering, search, and pagination."""

    def create(self, db: Session, transaction: FinancialTransaction) -> FinancialTransaction:
        db.add(transaction)
        db.flush()
        return transaction

    def get_by_id(
        self, db: Session, transaction_id: uuid.UUID, user_id: uuid.UUID
    ) -> FinancialTransaction | None:
        stmt = (
            select(FinancialTransaction)
            .options(
                joinedload(FinancialTransaction.account),
                joinedload(FinancialTransaction.category),
            )
            .where(
                FinancialTransaction.id == transaction_id,
                FinancialTransaction.user_id == user_id,
                FinancialTransaction.account.has(FinancialAccount.status != "disconnected"),
            )
        )
        return db.execute(stmt).scalar_one_or_none()

    def get_by_external_reference(
        self,
        db: Session,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
        external_reference: str,
    ) -> FinancialTransaction | None:
        stmt = select(FinancialTransaction).where(
            FinancialTransaction.user_id == user_id,
            FinancialTransaction.account_id == account_id,
            FinancialTransaction.external_reference == external_reference,
        )
        return db.execute(stmt).scalar_one_or_none()

    def list_transactions(
        self,
        db: Session,
        user_id: uuid.UUID,
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
    ) -> tuple[list[FinancialTransaction], int]:
        base_stmt = select(FinancialTransaction).where(
            FinancialTransaction.user_id == user_id,
            FinancialTransaction.account.has(FinancialAccount.status != "disconnected"),
        )

        if account_id:
            base_stmt = base_stmt.where(FinancialTransaction.account_id == account_id)
        if transaction_type:
            base_stmt = base_stmt.where(FinancialTransaction.transaction_type == transaction_type)
        if category_id:
            base_stmt = base_stmt.where(FinancialTransaction.category_id == category_id)
        if source:
            base_stmt = base_stmt.where(FinancialTransaction.source == source)
        if start_date:
            base_stmt = base_stmt.where(FinancialTransaction.transaction_date >= start_date)
        if end_date:
            base_stmt = base_stmt.where(FinancialTransaction.transaction_date <= end_date)
        if search:
            search_pattern = f"%{search.strip()}%"
            base_stmt = base_stmt.where(
                or_(
                    FinancialTransaction.description.ilike(search_pattern),
                    FinancialTransaction.merchant_payee.ilike(search_pattern),
                    FinancialTransaction.notes.ilike(search_pattern),
                )
            )

        # Count total matching records
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total = db.execute(count_stmt).scalar() or 0

        # Sort order
        if sort_by == "date_asc":
            order_clause = [
                FinancialTransaction.transaction_date.asc(),
                FinancialTransaction.created_at.asc(),
            ]
        elif sort_by == "amount_asc":
            order_clause = [FinancialTransaction.amount.asc()]
        elif sort_by == "amount_desc":
            order_clause = [FinancialTransaction.amount.desc()]
        else:  # default date_desc
            order_clause = [
                FinancialTransaction.transaction_date.desc(),
                FinancialTransaction.created_at.desc(),
            ]

        offset = max(0, (page - 1) * page_size)
        query = (
            base_stmt.options(
                joinedload(FinancialTransaction.account),
                joinedload(FinancialTransaction.category),
            )
            .order_by(*order_clause)
            .offset(offset)
            .limit(page_size)
        )

        items = list(db.execute(query).scalars().all())
        return items, total

    def update(self, db: Session, transaction: FinancialTransaction) -> FinancialTransaction:
        db.add(transaction)
        db.flush()
        return transaction

    def delete(self, db: Session, transaction: FinancialTransaction) -> None:
        db.delete(transaction)
        db.flush()
