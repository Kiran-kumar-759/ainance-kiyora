import datetime as dt
import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
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
    from app.models.finance import FinancialAccount, FinancialCategory, FinancialTransaction
    from app.models.user import User


class ImportBatch(Base):
    """
    Represents a single uploaded CSV or XLSX bank statement import session,
    tracking file metadata, lifecycle state machine, column mapping, and audit counts.
    """

    __tablename__ = "import_batches"

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
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    file_type: Mapped[str] = mapped_column(String(10), nullable=False)  # csv, xlsx
    storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(
        String(30), default="uploaded", index=True, nullable=False
    )  # uploaded, parsing, mapping_required, validating, ready_for_review, importing, completed, completed_with_errors, failed, cancelled

    sheet_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    header_row_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    delimiter: Mapped[str | None] = mapped_column(String(5), nullable=True)

    total_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    valid_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    invalid_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    needs_review_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duplicate_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    potential_duplicate_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    imported_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skipped_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    total_income: Mapped[Decimal] = mapped_column(
        Numeric(19, 2), default=Decimal("0.00"), nullable=False
    )
    total_expenses: Mapped[Decimal] = mapped_column(
        Numeric(19, 2), default=Decimal("0.00"), nullable=False
    )

    mapping_configuration: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    inspection_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    lifecycle_history: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, default=list, nullable=False
    )
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

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
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User")
    account: Mapped["FinancialAccount"] = relationship("FinancialAccount")
    rows: Mapped[list["ImportRow"]] = relationship(
        "ImportRow",
        back_populates="batch",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_import_batches_user_created", "user_id", "created_at"),
        Index("ix_import_batches_user_account_hash", "user_id", "account_id", "file_hash"),
    )


class ImportRow(Base):
    """
    Canonical normalized representation of an individual row parsed from a bank statement.
    Stores original raw JSON data, deterministic fingerprint, validation status, duplicate flags,
    and traceability link to the committed FinancialTransaction.
    """

    __tablename__ = "import_rows"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    import_batch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("import_batches.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    source_row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_row_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    normalized_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    normalized_description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    normalized_merchant: Mapped[str | None] = mapped_column(String(150), nullable=True)
    normalized_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_amount: Mapped[Decimal | None] = mapped_column(Numeric(19, 2), nullable=True)
    normalized_type: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # income, expense
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    transaction_reference: Mapped[str | None] = mapped_column(
        String(100), index=True, nullable=True
    )
    running_balance: Mapped[Decimal | None] = mapped_column(Numeric(19, 2), nullable=True)
    row_fingerprint: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)

    validation_status: Mapped[str] = mapped_column(
        String(30), default="valid", index=True, nullable=False
    )  # valid, invalid, needs_review, duplicate, potential_duplicate, excluded, imported
    duplicate_status: Mapped[str] = mapped_column(
        String(40), default="none", nullable=False
    )  # none, within_file_duplicate, existing_reference_duplicate, exact_match_duplicate, potential_duplicate, resolved_import, resolved_skip
    duplicate_match_transaction_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    duplicate_match_row_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)

    validation_errors: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("financial_categories.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_selected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    review_changes: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    imported_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("financial_transactions.id", ondelete="SET NULL"),
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

    # Relationships
    batch: Mapped["ImportBatch"] = relationship("ImportBatch", back_populates="rows")
    category: Mapped["FinancialCategory | None"] = relationship("FinancialCategory")
    imported_transaction: Mapped["FinancialTransaction | None"] = relationship(
        "FinancialTransaction", foreign_keys=[imported_transaction_id]
    )

    __table_args__ = (
        Index("ix_import_rows_batch_status", "import_batch_id", "validation_status"),
        Index("ix_import_rows_batch_row_num", "import_batch_id", "source_row_number"),
    )


class ImportMappingProfile(Base):
    """
    Reusable per-user bank statement column mapping profile (e.g. HDFC Savings CSV, SBI Excel).
    """

    __tablename__ = "import_mapping_profiles"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    profile_name: Mapped[str] = mapped_column(String(100), nullable=False)
    file_format: Mapped[str] = mapped_column(String(10), nullable=False)  # csv, xlsx
    mapping_configuration: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
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

    user: Mapped["User"] = relationship("User")
