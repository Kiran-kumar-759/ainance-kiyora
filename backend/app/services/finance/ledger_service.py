import datetime as dt
import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.finance import LedgerEntry, LedgerJournal
from app.repositories.finance.account_repository import AccountRepository
from app.repositories.finance.ledger_repository import LedgerRepository


class LedgerService:
    """
    Authoritative double-entry financial ledger service.
    Guarantees every posted journal has exactly balanced debits and credits:
    sum(debits) == sum(credits).
    """

    def __init__(self):
        self.ledger_repo = LedgerRepository()
        self.account_repo = AccountRepository()

    def post_opening_balance(
        self,
        db: Session,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
        account_type: str,
        amount: Decimal,
        entry_date: dt.date,
        currency: str = "INR",
    ) -> LedgerJournal | None:
        """
        Creates balanced opening balance journal lines.
        If amount is 0.00, no balance posting is needed.
        """
        if amount <= Decimal("0.00"):
            return None

        journal = LedgerJournal(
            user_id=user_id,
            journal_type="opening_balance",
            reference=f"OB-{account_id.hex[:8]}",
            description=f"Opening balance position for account {account_id}",
            entry_date=entry_date,
        )
        self.ledger_repo.create_journal(db, journal)

        if account_type == "credit_card":
            # Opening liability: Credit card account, Debit opening balance equity offset
            self.ledger_repo.add_entry(
                db,
                LedgerEntry(
                    journal_id=journal.id,
                    account_id=account_id,
                    entry_type="credit",
                    amount=amount,
                    currency=currency,
                    description="Opening credit liability",
                ),
            )
            self.ledger_repo.add_entry(
                db,
                LedgerEntry(
                    journal_id=journal.id,
                    account_id=None,  # Equity offset
                    entry_type="debit",
                    amount=amount,
                    currency=currency,
                    description="Opening balance equity offset",
                ),
            )
        else:
            # Asset account: Debit asset account, Credit opening balance equity offset
            self.ledger_repo.add_entry(
                db,
                LedgerEntry(
                    journal_id=journal.id,
                    account_id=account_id,
                    entry_type="debit",
                    amount=amount,
                    currency=currency,
                    description="Opening balance asset debit",
                ),
            )
            self.ledger_repo.add_entry(
                db,
                LedgerEntry(
                    journal_id=journal.id,
                    account_id=None,  # Equity offset
                    entry_type="credit",
                    amount=amount,
                    currency=currency,
                    description="Opening balance equity offset",
                ),
            )

        self.recalculate_and_sync_account_balance(db, account_id, account_type)
        return journal

    def post_transaction(
        self,
        db: Session,
        user_id: uuid.UUID,
        transaction_id: uuid.UUID,
        account_id: uuid.UUID,
        account_type: str,
        transaction_type: str,
        amount: Decimal,
        entry_date: dt.date,
        description: str,
        currency: str = "INR",
    ) -> LedgerJournal:
        """
        Creates a balanced journal entry for an income or expense transaction.
        """
        journal = LedgerJournal(
            user_id=user_id,
            transaction_id=transaction_id,
            journal_type=transaction_type,
            reference=f"TX-{transaction_id.hex[:8]}",
            description=description,
            entry_date=entry_date,
        )
        self.ledger_repo.create_journal(db, journal)

        if transaction_type == "income":
            if account_type == "credit_card":
                # Income / refund credited to a credit card reduces outstanding liability
                self.ledger_repo.add_entry(
                    db,
                    LedgerEntry(
                        journal_id=journal.id,
                        account_id=account_id,
                        entry_type="debit",  # Debit reduces liability
                        amount=amount,
                        currency=currency,
                        description=f"Refund/Credit to card: {description}",
                    ),
                )
                self.ledger_repo.add_entry(
                    db,
                    LedgerEntry(
                        journal_id=journal.id,
                        account_id=None,
                        entry_type="credit",
                        amount=amount,
                        currency=currency,
                        description="Income/Refund nominal offset",
                    ),
                )
            else:
                # Normal asset income: Debit asset (money in), Credit nominal income
                self.ledger_repo.add_entry(
                    db,
                    LedgerEntry(
                        journal_id=journal.id,
                        account_id=account_id,
                        entry_type="debit",
                        amount=amount,
                        currency=currency,
                        description=description,
                    ),
                )
                self.ledger_repo.add_entry(
                    db,
                    LedgerEntry(
                        journal_id=journal.id,
                        account_id=None,
                        entry_type="credit",
                        amount=amount,
                        currency=currency,
                        description="Income nominal offset",
                    ),
                )
        else:
            # Expense
            if account_type == "credit_card":
                # Expense on credit card increases liability: Credit card, Debit expense
                self.ledger_repo.add_entry(
                    db,
                    LedgerEntry(
                        journal_id=journal.id,
                        account_id=account_id,
                        entry_type="credit",  # Credit increases card liability
                        amount=amount,
                        currency=currency,
                        description=f"Card charge: {description}",
                    ),
                )
                self.ledger_repo.add_entry(
                    db,
                    LedgerEntry(
                        journal_id=journal.id,
                        account_id=None,
                        entry_type="debit",
                        amount=amount,
                        currency=currency,
                        description="Expense nominal offset",
                    ),
                )
            else:
                # Expense on asset: Credit asset (money out), Debit expense
                self.ledger_repo.add_entry(
                    db,
                    LedgerEntry(
                        journal_id=journal.id,
                        account_id=account_id,
                        entry_type="credit",
                        amount=amount,
                        currency=currency,
                        description=description,
                    ),
                )
                self.ledger_repo.add_entry(
                    db,
                    LedgerEntry(
                        journal_id=journal.id,
                        account_id=None,
                        entry_type="debit",
                        amount=amount,
                        currency=currency,
                        description="Expense nominal offset",
                    ),
                )

        self.recalculate_and_sync_account_balance(db, account_id, account_type)
        return journal

    def post_transfer(
        self,
        db: Session,
        user_id: uuid.UUID,
        transfer_id: uuid.UUID,
        source_account_id: uuid.UUID,
        source_account_type: str,
        dest_account_id: uuid.UUID,
        dest_account_type: str,
        amount: Decimal,
        entry_date: dt.date,
        description: str,
        currency: str = "INR",
    ) -> LedgerJournal:
        """
        Creates a balanced transfer journal between two accounts.
        Source account is credited (money leaves).
        Destination account is debited (money enters or card liability reduced).
        """
        journal = LedgerJournal(
            user_id=user_id,
            transfer_id=transfer_id,
            journal_type="transfer",
            reference=f"TR-{transfer_id.hex[:8]}",
            description=description or "Account Transfer",
            entry_date=entry_date,
        )
        self.ledger_repo.create_journal(db, journal)

        # Source line: Credit source account
        self.ledger_repo.add_entry(
            db,
            LedgerEntry(
                journal_id=journal.id,
                account_id=source_account_id,
                entry_type="credit",
                amount=amount,
                currency=currency,
                description=f"Transfer outgoing: {description}",
            ),
        )

        # Destination line: Debit destination account
        self.ledger_repo.add_entry(
            db,
            LedgerEntry(
                journal_id=journal.id,
                account_id=dest_account_id,
                entry_type="debit",
                amount=amount,
                currency=currency,
                description=f"Transfer incoming: {description}",
            ),
        )

        self.recalculate_and_sync_account_balance(db, source_account_id, source_account_type)
        self.recalculate_and_sync_account_balance(db, dest_account_id, dest_account_type)
        return journal

    def reverse_transaction_journal(
        self,
        db: Session,
        transaction_id: uuid.UUID,
        account_id: uuid.UUID,
        account_type: str,
    ) -> None:
        """Reverses the active journal for a transaction and syncs the account balance."""
        journal = self.ledger_repo.get_journal_by_transaction_id(db, transaction_id)
        if journal:
            journal.is_reversed = True
            db.add(journal)
            db.flush()
            self.recalculate_and_sync_account_balance(db, account_id, account_type)

    def reverse_transfer_journal(
        self,
        db: Session,
        transfer_id: uuid.UUID,
        source_account_id: uuid.UUID,
        source_account_type: str,
        dest_account_id: uuid.UUID,
        dest_account_type: str,
    ) -> None:
        """Reverses the active journal for a transfer and syncs both account balances."""
        journal = self.ledger_repo.get_journal_by_transfer_id(db, transfer_id)
        if journal:
            journal.is_reversed = True
            db.add(journal)
            db.flush()
            self.recalculate_and_sync_account_balance(db, source_account_id, source_account_type)
            self.recalculate_and_sync_account_balance(db, dest_account_id, dest_account_type)

    def recalculate_and_sync_account_balance(
        self, db: Session, account_id: uuid.UUID, account_type: str
    ) -> Decimal:
        """
        Calculates authoritative balance from unreversed ledger entries
        and updates the account record.
        """
        balance = self.ledger_repo.calculate_account_balance(db, account_id, account_type)
        self.account_repo.update_balance(db, account_id, balance)
        return balance
