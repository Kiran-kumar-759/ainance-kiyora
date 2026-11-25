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
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.documents import FinancialDocument
    from app.models.user import User


class EmailConnection(Base):
    """
    Encrypted user OAuth connection to an external email provider (Gmail first,
    extensible to other providers cleanly). Tokens are stored encrypted at rest
    using Fernet authenticated encryption and never serialized to frontend schemas.
    """

    __tablename__ = "email_connections"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(30), default="gmail", nullable=False)
    email_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(30), default="disconnected", index=True, nullable=False
    )  # disconnected, connected, error, revoked
    scopes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)

    encrypted_access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    encrypted_refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    last_history_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_sync_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

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
    sync_runs: Mapped[list["EmailSyncHistory"]] = relationship(
        "EmailSyncHistory",
        back_populates="connection",
        cascade="all, delete-orphan",
        order_by="EmailSyncHistory.started_at.desc()",
    )

    __table_args__ = (UniqueConstraint("user_id", "provider", name="uq_email_conn_user_provider"),)


class EmailSyncHistory(Base):
    """Audit trail of Gmail incremental/query synchronization runs and metrics."""

    __tablename__ = "email_sync_history"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("email_connections.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    sync_mode: Mapped[str] = mapped_column(
        String(30), default="full_query", nullable=False
    )  # full_query, incremental_history
    status: Mapped[str] = mapped_column(
        String(30), default="running", index=True, nullable=False
    )  # running, completed, partial, failed

    messages_scanned: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    relevant_messages: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    attachments_processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duplicate_candidates: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    candidates_needing_review: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_jobs: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    start_history_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    end_history_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
        nullable=False,
    )
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    connection: Mapped["EmailConnection"] = relationship(
        "EmailConnection", back_populates="sync_runs"
    )


class EmailMessageRecord(Base):
    """Sanitized metadata & extracted plain-text summary of a relevant financial email."""

    __tablename__ = "email_message_records"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("email_connections.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    provider_message_id: Mapped[str] = mapped_column(String(200), nullable=False)
    thread_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    sender: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(500), nullable=True)
    received_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    snippet_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    relevance_category: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
        nullable=False,
    )

    attachments: Mapped[list["EmailAttachmentRecord"]] = relationship(
        "EmailAttachmentRecord",
        back_populates="message",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("user_id", "provider_message_id", name="uq_email_msg_user_provider_msg"),
    )


class EmailAttachmentRecord(Base):
    """Links an email attachment to its privately stored FinancialDocument when supported."""

    __tablename__ = "email_attachment_records"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("email_message_records.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("financial_documents.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    provider_attachment_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    file_hash: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    is_supported: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    processing_status: Mapped[str] = mapped_column(
        String(30), default="pending", nullable=False
    )  # pending, stored, skipped, failed
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
        nullable=False,
    )

    message: Mapped["EmailMessageRecord"] = relationship(
        "EmailMessageRecord", back_populates="attachments"
    )
    document: Mapped["FinancialDocument | None"] = relationship("FinancialDocument")


class EmailDocumentCandidate(Base):
    """
    Reviewable candidate generated from a financial email + optional attachment/OCR.
    Never creates confirmed financial transactions or bills without explicit user confirmation.
    """

    __tablename__ = "email_document_candidates"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("email_connections.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("email_message_records.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    attachment_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("email_attachment_records.id", ondelete="SET NULL"),
        nullable=True,
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("financial_documents.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(30), default="needs_review", index=True, nullable=False
    )  # needs_review, duplicate_warning, confirmed, rejected
    duplicate_status: Mapped[str] = mapped_column(
        String(30), default="unique", nullable=False
    )  # unique, uncertain_duplicate, exact_duplicate
    duplicate_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    merchant_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    invoice_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    invoice_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(19, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), default="INR", nullable=True)
    extracted_summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

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
    reviewed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    message: Mapped["EmailMessageRecord"] = relationship("EmailMessageRecord")
    attachment: Mapped["EmailAttachmentRecord | None"] = relationship("EmailAttachmentRecord")
    document: Mapped["FinancialDocument | None"] = relationship("FinancialDocument")

    __table_args__ = (
        Index("ix_email_cand_user_status", "user_id", "status"),
    )
