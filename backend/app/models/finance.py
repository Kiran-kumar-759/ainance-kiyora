import datetime as dt
import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class FinancialAccount(Base):
    """
    User-owned financial account (e.g. Bank Savings, Current, Cash Wallet, Credit Card).
    Balances are exact decimal (NUMERIC 19,2).
    """

    __tablename__ = "financial_accounts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    account_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )  # savings, current, cash, credit_card, digital_wallet, other
    institution_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    account_identifier: Mapped[str | None] = mapped_column(String(50), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    opening_balance: Mapped[Decimal] = mapped_column(
        Numeric(19, 2),
        default=Decimal("0.00"),
        nullable=False,
    )
    current_balance: Mapped[Decimal] = mapped_column(
        Numeric(19, 2),
        default=Decimal("0.00"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20), default="active", nullable=False
    )  # active, archived
    source: Mapped[str] = mapped_column(
        String(30), default="manual", nullable=False
    )  # manual, demo_bank
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
        nullable=False,
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
        onupdate=lambda: dt.datetime.now(dt.UTC),
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="accounts")
    transactions: Mapped[list["FinancialTransaction"]] = relationship(
        "FinancialTransaction",
        back_populates="account",
        cascade="all, delete-orphan",
    )
    ledger_entries: Mapped[list["LedgerEntry"]] = relationship(
        "LedgerEntry",
        back_populates="account",
    )

    __table_args__ = (Index("ix_financial_accounts_user_status", "user_id", "status"),)


class FinancialCategory(Base):
    """
    Transaction category.
    System categories have user_id = NULL.
    Custom categories belong to a specific user.
    """

    __tablename__ = "financial_categories"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    category_type: Mapped[str] = mapped_column(String(20), nullable=False)  # income, expense
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)
    color: Mapped[str | None] = mapped_column(String(30), nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
        nullable=False,
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
        onupdate=lambda: dt.datetime.now(dt.UTC),
        nullable=False,
    )

    user: Mapped["User | None"] = relationship("User", back_populates="categories")
    transactions: Mapped[list["FinancialTransaction"]] = relationship(
        "FinancialTransaction",
        back_populates="category",
    )

    __table_args__ = (Index("ix_financial_categories_user_type", "user_id", "category_type"),)


class FinancialTransfer(Base):
    """
    First-class representation of an atomic money transfer between two user-owned accounts.
    """

    __tablename__ = "financial_transfers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    source_account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("financial_accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    destination_account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("financial_accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(19, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    transfer_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="completed", nullable=False
    )  # completed, reversed
    reversal_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reversed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_transaction_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    destination_transaction_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
        nullable=False,
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
        onupdate=lambda: dt.datetime.now(dt.UTC),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="transfers")
    source_account: Mapped["FinancialAccount"] = relationship(
        "FinancialAccount", foreign_keys=[source_account_id]
    )
    destination_account: Mapped["FinancialAccount"] = relationship(
        "FinancialAccount", foreign_keys=[destination_account_id]
    )
    transactions: Mapped[list["FinancialTransaction"]] = relationship(
        "FinancialTransaction",
        back_populates="transfer",
        cascade="all, delete-orphan",
    )
    journals: Mapped[list["LedgerJournal"]] = relationship(
        "LedgerJournal",
        back_populates="transfer",
        cascade="all, delete-orphan",
    )


class FinancialTransaction(Base):
    """
    Individual financial transaction (Income, Expense, or side of a Transfer).
    """

    __tablename__ = "financial_transactions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("financial_accounts.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    transaction_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # income, expense, transfer
    amount: Mapped[Decimal] = mapped_column(Numeric(19, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("financial_categories.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    merchant_payee: Mapped[str | None] = mapped_column(String(150), nullable=True)
    transaction_date: Mapped[dt.date] = mapped_column(Date, index=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(
        String(30), default="manual", nullable=False
    )  # manual, demo_bank, csv_import, xlsx_import
    external_reference: Mapped[str | None] = mapped_column(String(100), index=True, nullable=True)
    import_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("import_batches.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    import_row_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True, nullable=True)
    transfer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("financial_transfers.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
        nullable=False,
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
        onupdate=lambda: dt.datetime.now(dt.UTC),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="transactions")
    account: Mapped["FinancialAccount"] = relationship(
        "FinancialAccount", back_populates="transactions"
    )
    category: Mapped["FinancialCategory | None"] = relationship(
        "FinancialCategory", back_populates="transactions"
    )
    transfer: Mapped["FinancialTransfer | None"] = relationship(
        "FinancialTransfer", back_populates="transactions"
    )
    journals: Mapped[list["LedgerJournal"]] = relationship(
        "LedgerJournal",
        back_populates="transaction",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index(
            "ix_financial_transactions_user_date",
            "user_id",
            "transaction_date",
        ),
        Index(
            "ix_financial_transactions_user_account_date",
            "user_id",
            "account_id",
            "transaction_date",
        ),
        Index(
            "uq_transactions_user_account_ext_ref",
            "user_id",
            "account_id",
            "external_reference",
            unique=True,
            postgresql_where=(external_reference.isnot(None)),
        ),
    )


class LedgerJournal(Base):
    """
    Balanced double-entry journal entry.
    Each journal must have sum(debits) == sum(credits).
    """

    __tablename__ = "ledger_journals"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("financial_transactions.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    transfer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("financial_transfers.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    journal_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # opening_balance, income, expense, transfer, reversal
    reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    entry_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    is_reversed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="journals")
    entries: Mapped[list["LedgerEntry"]] = relationship(
        "LedgerEntry",
        back_populates="journal",
        cascade="all, delete-orphan",
    )
    transaction: Mapped["FinancialTransaction | None"] = relationship(
        "FinancialTransaction", back_populates="journals"
    )
    transfer: Mapped["FinancialTransfer | None"] = relationship(
        "FinancialTransfer", back_populates="journals"
    )


class LedgerEntry(Base):
    """
    Individual debit or credit posting inside a balanced LedgerJournal.
    account_id is NULL for external nominal balancing lines (e.g. Income/Expense/Equity offset).
    """

    __tablename__ = "ledger_entries"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    journal_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("ledger_journals.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("financial_accounts.id", ondelete="RESTRICT"),
        index=True,
        nullable=True,
    )
    entry_type: Mapped[str] = mapped_column(String(10), nullable=False)  # debit, credit
    amount: Mapped[Decimal] = mapped_column(Numeric(19, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
        nullable=False,
    )

    journal: Mapped["LedgerJournal"] = relationship("LedgerJournal", back_populates="entries")
    account: Mapped["FinancialAccount | None"] = relationship(
        "FinancialAccount", back_populates="ledger_entries"
    )


class BankingConnection(Base):
    """
    Simulated or real banking provider connection for an authenticated user.
    """

    __tablename__ = "banking_connections"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    provider_id: Mapped[str] = mapped_column(
        String(50), index=True, nullable=False
    )  # demo_national_bank, demo_private_bank, demo_digital_bank
    institution_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="connected", nullable=False
    )  # connected, disconnected, error
    consent_granted_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
        nullable=False,
    )
    consent_scope: Mapped[str] = mapped_column(
        String(100), default="accounts,transactions", nullable=False
    )
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_sync_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
        nullable=False,
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
        onupdate=lambda: dt.datetime.now(dt.UTC),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="banking_connections")
    sync_runs: Mapped[list["BankingSyncRun"]] = relationship(
        "BankingSyncRun",
        back_populates="connection",
        cascade="all, delete-orphan",
    )


class BankingSyncRun(Base):
    """
    Audit record of each banking synchronization attempt.
    """

    __tablename__ = "banking_sync_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    connection_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("banking_connections.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20), default="success", nullable=False
    )  # success, failed, partial
    accounts_synced: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    transactions_synced: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
        nullable=False,
    )
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    connection: Mapped["BankingConnection"] = relationship(
        "BankingConnection", back_populates="sync_runs"
    )
    user: Mapped["User"] = relationship("User")
