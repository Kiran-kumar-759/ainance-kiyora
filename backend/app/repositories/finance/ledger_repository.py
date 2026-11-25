import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.finance import LedgerEntry, LedgerJournal


class LedgerRepository:
    """Repository for balanced double-entry journals and entries with strict audit integrity."""

    def create_journal(self, db: Session, journal: LedgerJournal) -> LedgerJournal:
        db.add(journal)
        db.flush()
        return journal

    def add_entry(self, db: Session, entry: LedgerEntry) -> LedgerEntry:
        db.add(entry)
        db.flush()
        return entry

    def get_journal_by_transaction_id(
        self, db: Session, transaction_id: uuid.UUID
    ) -> LedgerJournal | None:
        stmt = select(LedgerJournal).where(
            LedgerJournal.transaction_id == transaction_id,
            LedgerJournal.is_reversed.is_(False),
        )
        return db.execute(stmt).scalar_one_or_none()

    def get_journal_by_transfer_id(
        self, db: Session, transfer_id: uuid.UUID
    ) -> LedgerJournal | None:
        stmt = select(LedgerJournal).where(
            LedgerJournal.transfer_id == transfer_id,
            LedgerJournal.is_reversed.is_(False),
        )
        return db.execute(stmt).scalar_one_or_none()

    def calculate_account_balance(
        self, db: Session, account_id: uuid.UUID, account_type: str
    ) -> Decimal:
        """
        Calculates authoritative balance directly from active unreversed ledger entries.
        For Asset accounts: Balance = Total Debits - Total Credits.
        For Credit Cards (Liabilities): Outstanding Liability = Total Credits - Total Debits.
        """
        # Sum of debits
        debit_stmt = (
            select(func.coalesce(func.sum(LedgerEntry.amount), Decimal("0.00")))
            .join(LedgerJournal, LedgerEntry.journal_id == LedgerJournal.id)
            .where(
                LedgerEntry.account_id == account_id,
                LedgerEntry.entry_type == "debit",
                LedgerJournal.is_reversed.is_(False),
            )
        )
        total_debits = db.execute(debit_stmt).scalar() or Decimal("0.00")

        # Sum of credits
        credit_stmt = (
            select(func.coalesce(func.sum(LedgerEntry.amount), Decimal("0.00")))
            .join(LedgerJournal, LedgerEntry.journal_id == LedgerJournal.id)
            .where(
                LedgerEntry.account_id == account_id,
                LedgerEntry.entry_type == "credit",
                LedgerJournal.is_reversed.is_(False),
            )
        )
        total_credits = db.execute(credit_stmt).scalar() or Decimal("0.00")

        if account_type in {"credit_card", "loan_liability"}:
            # Outstanding liability owed
            return Decimal(total_credits - total_debits)
        else:
            # Asset account (Savings, Current, Cash, Wallet, Other)
            return Decimal(total_debits - total_credits)
