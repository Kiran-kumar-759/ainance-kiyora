import datetime as dt
import uuid
from decimal import Decimal

from sqlalchemy import Date, and_, cast, exists, func, not_, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.finance import (
    FinancialAccount,
    FinancialCategory,
    FinancialTransaction,
    FinancialTransfer,
    LedgerEntry,
    LedgerJournal,
)


class AnalyticsRepository:
    """
    PostgreSQL aggregation repository for Phase 4 analytics and reporting.
    All queries apply strict user isolation, exclude disconnected demo accounts,
    exclude transfer legs from income/expense math, and exclude reversed journals.
    """

    def _active_journal_clause(self):
        """
        Ensures transactions whose ONLY ledger journals are reversed are excluded,
        while preserving transactions that have an active (unreversed) journal
        (including edited transactions where old journal is reversed and a new active one exists).
        """
        has_reversed = exists(
            select(LedgerJournal.id).where(
                LedgerJournal.transaction_id == FinancialTransaction.id,
                LedgerJournal.is_reversed.is_(True),
            )
        )
        has_active = exists(
            select(LedgerJournal.id).where(
                LedgerJournal.transaction_id == FinancialTransaction.id,
                LedgerJournal.is_reversed.is_(False),
            )
        )
        return not_(and_(has_reversed, not_(has_active)))

    def _base_ie_filters(
        self,
        user_id: uuid.UUID,
        start_date: dt.date,
        end_date: dt.date,
        account_id: uuid.UUID | None = None,
        category_id: uuid.UUID | None = None,
        source: str | None = None,
        transaction_type: str | None = None,
    ) -> list:
        clauses = [
            FinancialTransaction.user_id == user_id,
            FinancialTransaction.transfer_id.is_(None),
            FinancialTransaction.transaction_date >= start_date,
            FinancialTransaction.transaction_date <= end_date,
            FinancialAccount.status != "disconnected",
            self._active_journal_clause(),
        ]
        if transaction_type in {"income", "expense"}:
            clauses.append(FinancialTransaction.transaction_type == transaction_type)
        else:
            clauses.append(FinancialTransaction.transaction_type.in_(["income", "expense"]))
        if account_id is not None:
            clauses.append(FinancialTransaction.account_id == account_id)
        if category_id is not None:
            clauses.append(FinancialTransaction.category_id == category_id)
        if source:
            clauses.append(FinancialTransaction.source == source)
        return clauses

    def get_earliest_transaction_date(self, db: Session, user_id: uuid.UUID) -> dt.date | None:
        stmt = (
            select(func.min(FinancialTransaction.transaction_date))
            .join(FinancialAccount, FinancialTransaction.account_id == FinancialAccount.id)
            .where(
                FinancialTransaction.user_id == user_id,
                FinancialAccount.status != "disconnected",
                self._active_journal_clause(),
            )
        )
        return db.execute(stmt).scalar()

    def get_period_totals(
        self,
        db: Session,
        user_id: uuid.UUID,
        start_date: dt.date,
        end_date: dt.date,
        account_id: uuid.UUID | None = None,
        category_id: uuid.UUID | None = None,
        source: str | None = None,
        transaction_type: str | None = None,
    ) -> dict[str, Decimal | int]:
        clauses = self._base_ie_filters(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            account_id=account_id,
            category_id=category_id,
            source=source,
            transaction_type=transaction_type,
        )
        stmt = (
            select(
                FinancialTransaction.transaction_type,
                func.coalesce(func.sum(FinancialTransaction.amount), Decimal("0.00")),
                func.count(FinancialTransaction.id),
            )
            .join(FinancialAccount, FinancialTransaction.account_id == FinancialAccount.id)
            .where(*clauses)
            .group_by(FinancialTransaction.transaction_type)
        )
        income = Decimal("0.00")
        expenses = Decimal("0.00")
        income_count = 0
        expense_count = 0

        for tx_type, total_amt, cnt in db.execute(stmt).all():
            amt = Decimal(total_amt or 0)
            if tx_type == "income":
                income = amt
                income_count = int(cnt or 0)
            elif tx_type == "expense":
                expenses = amt
                expense_count = int(cnt or 0)

        return {
            "income": income,
            "expenses": expenses,
            "income_count": income_count,
            "expense_count": expense_count,
            "total_count": income_count + expense_count,
        }

    def get_excluded_counts(
        self,
        db: Session,
        user_id: uuid.UUID,
        start_date: dt.date,
        end_date: dt.date,
        account_id: uuid.UUID | None = None,
    ) -> tuple[int, int]:
        """Counts excluded transfer transactions and reversed entries for calculation traceability."""
        tr_clauses = [
            FinancialTransaction.user_id == user_id,
            FinancialTransaction.transaction_date >= start_date,
            FinancialTransaction.transaction_date <= end_date,
            FinancialAccount.status != "disconnected",
            or_(
                FinancialTransaction.transaction_type == "transfer",
                FinancialTransaction.transfer_id.isnot(None),
            ),
        ]
        if account_id is not None:
            tr_clauses.append(FinancialTransaction.account_id == account_id)

        excluded_transfers = (
            db.execute(
                select(func.count(FinancialTransaction.id))
                .join(FinancialAccount, FinancialTransaction.account_id == FinancialAccount.id)
                .where(*tr_clauses)
            ).scalar()
            or 0
        )

        # Count reversed journals in date range belonging to user (reversed transactions/transfers)
        rev_stmt = select(func.count(LedgerJournal.id)).where(
            LedgerJournal.user_id == user_id,
            LedgerJournal.is_reversed.is_(True),
            LedgerJournal.entry_date >= start_date,
            LedgerJournal.entry_date <= end_date,
        )
        excluded_reversed = db.execute(rev_stmt).scalar() or 0
        return int(excluded_transfers), int(excluded_reversed)

    def get_category_breakdown(
        self,
        db: Session,
        user_id: uuid.UUID,
        transaction_type: str,
        start_date: dt.date,
        end_date: dt.date,
        account_id: uuid.UUID | None = None,
        source: str | None = None,
        category_id: uuid.UUID | None = None,
    ) -> list[dict]:
        clauses = self._base_ie_filters(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            account_id=account_id,
            category_id=category_id,
            source=source,
            transaction_type=transaction_type,
        )
        stmt = (
            select(
                FinancialTransaction.category_id,
                func.coalesce(FinancialCategory.name, "Uncategorized").label("cat_name"),
                FinancialCategory.color.label("cat_color"),
                func.coalesce(func.sum(FinancialTransaction.amount), Decimal("0.00")).label("total"),
                func.count(FinancialTransaction.id).label("tx_count"),
            )
            .join(FinancialAccount, FinancialTransaction.account_id == FinancialAccount.id)
            .outerjoin(FinancialCategory, FinancialTransaction.category_id == FinancialCategory.id)
            .where(*clauses)
            .group_by(
                FinancialTransaction.category_id,
                FinancialCategory.name,
                FinancialCategory.color,
            )
            .order_by(func.sum(FinancialTransaction.amount).desc())
        )
        rows = db.execute(stmt).all()
        return [
            {
                "category_id": r[0],
                "category_name": r[1],
                "category_color": r[2] or "#64748b",
                "total_amount": Decimal(r[3] or 0),
                "transaction_count": int(r[4] or 0),
            }
            for r in rows
        ]

    def get_account_breakdown(
        self,
        db: Session,
        user_id: uuid.UUID,
        transaction_type: str,
        start_date: dt.date,
        end_date: dt.date,
        category_id: uuid.UUID | None = None,
        source: str | None = None,
    ) -> list[dict]:
        clauses = self._base_ie_filters(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            category_id=category_id,
            source=source,
            transaction_type=transaction_type,
        )
        stmt = (
            select(
                FinancialAccount.id,
                FinancialAccount.name,
                FinancialAccount.account_type,
                func.coalesce(func.sum(FinancialTransaction.amount), Decimal("0.00")).label("total"),
                func.count(FinancialTransaction.id).label("tx_count"),
            )
            .join(FinancialAccount, FinancialTransaction.account_id == FinancialAccount.id)
            .where(*clauses)
            .group_by(
                FinancialAccount.id,
                FinancialAccount.name,
                FinancialAccount.account_type,
            )
            .order_by(func.sum(FinancialTransaction.amount).desc())
        )
        return [
            {
                "account_id": r[0],
                "account_name": r[1],
                "account_type": r[2],
                "total_amount": Decimal(r[3] or 0),
                "transaction_count": int(r[4] or 0),
            }
            for r in db.execute(stmt).all()
        ]

    def get_source_distribution(
        self,
        db: Session,
        user_id: uuid.UUID,
        transaction_type: str,
        start_date: dt.date,
        end_date: dt.date,
        account_id: uuid.UUID | None = None,
    ) -> list[dict]:
        clauses = self._base_ie_filters(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            account_id=account_id,
            transaction_type=transaction_type,
        )
        stmt = (
            select(
                FinancialTransaction.source,
                func.coalesce(func.sum(FinancialTransaction.amount), Decimal("0.00")),
                func.count(FinancialTransaction.id),
            )
            .join(FinancialAccount, FinancialTransaction.account_id == FinancialAccount.id)
            .where(*clauses)
            .group_by(FinancialTransaction.source)
            .order_by(func.sum(FinancialTransaction.amount).desc())
        )
        return [
            {
                "source": r[0],
                "total_amount": Decimal(r[1] or 0),
                "transaction_count": int(r[2] or 0),
            }
            for r in db.execute(stmt).all()
        ]

    def get_grouped_time_series(
        self,
        db: Session,
        user_id: uuid.UUID,
        start_date: dt.date,
        end_date: dt.date,
        granularity: str,
        account_id: uuid.UUID | None = None,
        category_id: uuid.UUID | None = None,
        source: str | None = None,
    ) -> list[dict]:
        """Single-query SQL date_trunc aggregation grouped by bucket and transaction_type."""
        clauses = self._base_ie_filters(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            account_id=account_id,
            category_id=category_id,
            source=source,
        )
        bucket_expr = cast(
            func.date_trunc(granularity, FinancialTransaction.transaction_date),
            Date,
        )
        stmt = (
            select(
                bucket_expr.label("bucket"),
                FinancialTransaction.transaction_type,
                func.coalesce(func.sum(FinancialTransaction.amount), Decimal("0.00")),
            )
            .join(FinancialAccount, FinancialTransaction.account_id == FinancialAccount.id)
            .where(*clauses)
            .group_by(bucket_expr, FinancialTransaction.transaction_type)
            .order_by(bucket_expr.asc())
        )
        return [
            {
                "bucket": r[0],
                "transaction_type": r[1],
                "total_amount": Decimal(r[2] or 0),
            }
            for r in db.execute(stmt).all()
        ]

    def get_account_period_activity_map(
        self,
        db: Session,
        user_id: uuid.UUID,
        start_date: dt.date,
        end_date: dt.date,
    ) -> dict[uuid.UUID, dict[str, Decimal | int]]:
        """Aggregates income, expenses, and transaction counts per account in one SQL query."""
        clauses = self._base_ie_filters(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
        )
        stmt = (
            select(
                FinancialTransaction.account_id,
                FinancialTransaction.transaction_type,
                func.coalesce(func.sum(FinancialTransaction.amount), Decimal("0.00")),
                func.count(FinancialTransaction.id),
            )
            .join(FinancialAccount, FinancialTransaction.account_id == FinancialAccount.id)
            .where(*clauses)
            .group_by(FinancialTransaction.account_id, FinancialTransaction.transaction_type)
        )
        result: dict[uuid.UUID, dict[str, Decimal | int]] = {}
        for acc_id, tx_type, total_amt, cnt in db.execute(stmt).all():
            entry = result.setdefault(
                acc_id,
                {"income": Decimal("0.00"), "expenses": Decimal("0.00"), "count": 0},
            )
            if tx_type == "income":
                entry["income"] = Decimal(total_amt or 0)
            elif tx_type == "expense":
                entry["expenses"] = Decimal(total_amt or 0)
            entry["count"] = int(entry["count"]) + int(cnt or 0)
        return result

    def get_largest_transactions(
        self,
        db: Session,
        user_id: uuid.UUID,
        transaction_type: str,
        start_date: dt.date,
        end_date: dt.date,
        account_id: uuid.UUID | None = None,
        limit: int = 8,
    ) -> list[FinancialTransaction]:
        clauses = self._base_ie_filters(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            account_id=account_id,
            transaction_type=transaction_type,
        )
        stmt = (
            select(FinancialTransaction)
            .options(
                joinedload(FinancialTransaction.account),
                joinedload(FinancialTransaction.category),
            )
            .join(FinancialAccount, FinancialTransaction.account_id == FinancialAccount.id)
            .where(*clauses)
            .order_by(FinancialTransaction.amount.desc(), FinancialTransaction.transaction_date.desc())
            .limit(limit)
        )
        return list(db.execute(stmt).scalars().all())

    def get_ledger_balance_deltas_by_date(
        self,
        db: Session,
        user_id: uuid.UUID,
        end_date: dt.date,
        account_id: uuid.UUID | None = None,
    ) -> list[dict]:
        """
        Queries unreversed double-entry LedgerEntry rows grouped by entry_date and account_type
        for deterministic historical balance reconstruction without fabricated snapshots.
        """
        clauses = [
            LedgerJournal.user_id == user_id,
            LedgerJournal.is_reversed.is_(False),
            LedgerJournal.entry_date <= end_date,
            LedgerEntry.account_id.isnot(None),
            FinancialAccount.status == "active",
        ]
        if account_id is not None:
            clauses.append(LedgerEntry.account_id == account_id)

        stmt = (
            select(
                LedgerJournal.entry_date,
                FinancialAccount.account_type,
                LedgerEntry.entry_type,
                func.coalesce(func.sum(LedgerEntry.amount), Decimal("0.00")),
            )
            .join(LedgerEntry, LedgerJournal.id == LedgerEntry.journal_id)
            .join(FinancialAccount, LedgerEntry.account_id == FinancialAccount.id)
            .where(*clauses)
            .group_by(
                LedgerJournal.entry_date,
                FinancialAccount.account_type,
                LedgerEntry.entry_type,
            )
            .order_by(LedgerJournal.entry_date.asc())
        )
        return [
            {
                "entry_date": r[0],
                "account_type": r[1],
                "entry_type": r[2],
                "amount": Decimal(r[3] or 0),
            }
            for r in db.execute(stmt).all()
        ]

    def list_report_transactions(
        self,
        db: Session,
        user_id: uuid.UUID,
        start_date: dt.date,
        end_date: dt.date,
        account_id: uuid.UUID | None = None,
        transaction_type: str | None = None,
        category_id: uuid.UUID | None = None,
        source: str | None = None,
        include_transfers: bool = False,
        limit: int = 5000,
    ) -> list[FinancialTransaction]:
        if include_transfers and not category_id:
            # Used for account_activity / transaction_summary when user asks for transfers too
            clauses = [
                FinancialTransaction.user_id == user_id,
                FinancialTransaction.transaction_date >= start_date,
                FinancialTransaction.transaction_date <= end_date,
                FinancialAccount.status != "disconnected",
                self._active_journal_clause(),
                ~exists(
                    select(FinancialTransfer.id).where(
                        FinancialTransfer.id == FinancialTransaction.transfer_id,
                        FinancialTransfer.status == "reversed",
                    )
                ),
            ]
            if account_id is not None:
                clauses.append(FinancialTransaction.account_id == account_id)
            if transaction_type in {"income", "expense", "transfer"}:
                clauses.append(FinancialTransaction.transaction_type == transaction_type)
            if source:
                clauses.append(FinancialTransaction.source == source)
        else:
            clauses = self._base_ie_filters(
                user_id=user_id,
                start_date=start_date,
                end_date=end_date,
                account_id=account_id,
                category_id=category_id,
                source=source,
                transaction_type=transaction_type,
            )

        stmt = (
            select(FinancialTransaction)
            .options(
                joinedload(FinancialTransaction.account),
                joinedload(FinancialTransaction.category),
            )
            .join(FinancialAccount, FinancialTransaction.account_id == FinancialAccount.id)
            .where(*clauses)
            .order_by(
                FinancialTransaction.transaction_date.desc(),
                FinancialTransaction.created_at.desc(),
            )
            .limit(limit)
        )
        return list(db.execute(stmt).scalars().all())
