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
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.bills import Bill
    from app.models.finance import FinancialTransaction
    from app.models.loans import Loan
    from app.models.subscriptions import Subscription
    from app.models.user import User


class FinancialDocument(Base):
    """
    User-owned private financial document (PDF, JPG, JPEG, PNG, WebP) stored with an
    opaque UUID storage key and SHA-256 hash. Original uploaded file bytes are immutable.
    """

    __tablename__ = "financial_documents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)

    document_category: Mapped[str] = mapped_column(
        String(40), default="other", index=True, nullable=False
    )
    source: Mapped[str] = mapped_column(
        String(30), default="manual_upload", nullable=False
    )  # manual_upload, gmail_attachment

    is_duplicate_of_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("financial_documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    duplicate_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    processing_status: Mapped[str] = mapped_column(
        String(30), default="uploaded", index=True, nullable=False
    )  # uploaded, queued, processing, extracted, needs_review, confirmed, rejected, failed
    ocr_status: Mapped[str] = mapped_column(
        String(30), default="pending", index=True, nullable=False
    )  # pending, queued, processing, completed, failed, skipped
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
        index=True,
        nullable=False,
    )
    processed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
        onupdate=lambda: dt.datetime.now(dt.UTC),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User")
    extraction: Mapped["DocumentExtraction | None"] = relationship(
        "DocumentExtraction",
        back_populates="document",
        uselist=False,
        cascade="all, delete-orphan",
    )
    jobs: Mapped[list["DocumentProcessingJob"]] = relationship(
        "DocumentProcessingJob",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentProcessingJob.created_at.desc()",
    )
    review_events: Mapped[list["DocumentReviewEvent"]] = relationship(
        "DocumentReviewEvent",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentReviewEvent.created_at.desc()",
    )
    links: Mapped[list["DocumentLink"]] = relationship(
        "DocumentLink",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentLink.created_at.desc()",
    )

    __table_args__ = (
        Index("ix_fin_docs_user_hash", "user_id", "file_hash"),
        Index("ix_fin_docs_user_status_date", "user_id", "processing_status", "uploaded_at"),
    )


class DocumentProcessingJob(Base):
    """
    PostgreSQL-backed asynchronous OCR & extraction job queue entry supporting
    FOR UPDATE SKIP LOCKED worker claims, crash recovery, and bounded retries.
    """

    __tablename__ = "document_processing_jobs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("financial_documents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    job_type: Mapped[str] = mapped_column(
        String(40), default="ocr_extract", nullable=False
    )  # ocr_extract, reprocess_ocr
    status: Mapped[str] = mapped_column(
        String(30), default="queued", index=True, nullable=False
    )  # queued, processing, completed, failed, cancelled
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    next_retry_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), index=True, nullable=True
    )
    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    worker_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(120), unique=True, nullable=True)

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

    document: Mapped["FinancialDocument"] = relationship("FinancialDocument", back_populates="jobs")

    __table_args__ = (
        Index(
            "uq_doc_job_active_per_doc",
            "document_id",
            "job_type",
            unique=True,
            postgresql_where=text("status IN ('queued', 'processing')"),
        ),
    )


class DocumentExtraction(Base):
    """
    Stores both immutable raw OCR text/structured snapshots and user-reviewable
    structured invoice, tax (Indian GST), and line-item fields.
    Unknown monetary values stay NULL (never coerced to ₹0.00).
    """

    __tablename__ = "document_extractions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("financial_documents.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    ocr_engine: Mapped[str] = mapped_column(String(40), nullable=False)
    ocr_engine_version: Mapped[str | None] = mapped_column(String(60), nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_structured_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Invoice metadata
    merchant_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    merchant_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    merchant_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    invoice_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    invoice_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    payment_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    bill_period: Mapped[str | None] = mapped_column(String(100), nullable=True)
    detected_document_type: Mapped[str | None] = mapped_column(String(40), nullable=True)

    # Financial amounts (nullable NUMERIC(19, 2))
    currency: Mapped[str | None] = mapped_column(String(3), default="INR", nullable=True)
    subtotal: Mapped[Decimal | None] = mapped_column(Numeric(19, 2), nullable=True)
    taxable_amount: Mapped[Decimal | None] = mapped_column(Numeric(19, 2), nullable=True)
    total_tax: Mapped[Decimal | None] = mapped_column(Numeric(19, 2), nullable=True)
    grand_total: Mapped[Decimal | None] = mapped_column(Numeric(19, 2), nullable=True)
    amount_paid: Mapped[Decimal | None] = mapped_column(Numeric(19, 2), nullable=True)
    outstanding_amount: Mapped[Decimal | None] = mapped_column(Numeric(19, 2), nullable=True)

    # Indian GST fields
    gstin: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cgst: Mapped[Decimal | None] = mapped_column(Numeric(19, 2), nullable=True)
    sgst: Mapped[Decimal | None] = mapped_column(Numeric(19, 2), nullable=True)
    igst: Mapped[Decimal | None] = mapped_column(Numeric(19, 2), nullable=True)
    tax_percentage: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)

    line_items: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    field_confidence: Mapped[dict[str, float]] = mapped_column(JSON, default=dict, nullable=False)
    field_decisions: Mapped[dict[str, str]] = mapped_column(JSON, default=dict, nullable=False)
    validation_errors: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    validation_warnings: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    processing_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    overall_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)

    extracted_at: Mapped[dt.datetime] = mapped_column(
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

    document: Mapped["FinancialDocument"] = relationship(
        "FinancialDocument", back_populates="extraction"
    )


class DocumentReviewEvent(Base):
    """Append-only human review & correction audit log for traceability."""

    __tablename__ = "document_review_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("financial_documents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    changes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
        nullable=False,
    )

    document: Mapped["FinancialDocument"] = relationship(
        "FinancialDocument", back_populates="review_events"
    )


class DocumentLink(Base):
    """
    Links a confirmed financial document to an existing Bill, Transaction, Subscription,
    or Loan (or records the entity created from confirmation to prevent duplicates).
    """

    __tablename__ = "document_links"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("financial_documents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    target_type: Mapped[str] = mapped_column(
        String(30), index=True, nullable=False
    )  # bill, transaction, subscription, loan
    link_role: Mapped[str] = mapped_column(
        String(30), default="supporting_document", nullable=False
    )  # supporting_document, created_from_document

    bill_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("bills.id", ondelete="CASCADE"), index=True, nullable=True
    )
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("financial_transactions.id", ondelete="CASCADE"), index=True, nullable=True
    )
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("subscriptions.id", ondelete="CASCADE"), index=True, nullable=True
    )
    loan_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("loans.id", ondelete="CASCADE"), index=True, nullable=True
    )

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
        nullable=False,
    )

    document: Mapped["FinancialDocument"] = relationship(
        "FinancialDocument", back_populates="links"
    )
    bill: Mapped["Bill | None"] = relationship("Bill")
    transaction: Mapped["FinancialTransaction | None"] = relationship("FinancialTransaction")
    subscription: Mapped["Subscription | None"] = relationship("Subscription")
    loan: Mapped["Loan | None"] = relationship("Loan")

    __table_args__ = (
        Index(
            "uq_doc_link_bill",
            "document_id",
            "bill_id",
            unique=True,
            postgresql_where=text("bill_id IS NOT NULL"),
        ),
        Index(
            "uq_doc_link_tx",
            "document_id",
            "transaction_id",
            unique=True,
            postgresql_where=text("transaction_id IS NOT NULL"),
        ),
        Index(
            "uq_doc_link_sub",
            "document_id",
            "subscription_id",
            unique=True,
            postgresql_where=text("subscription_id IS NOT NULL"),
        ),
        Index(
            "uq_doc_link_loan",
            "document_id",
            "loan_id",
            unique=True,
            postgresql_where=text("loan_id IS NOT NULL"),
        ),
    )
