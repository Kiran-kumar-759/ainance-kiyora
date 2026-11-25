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
    from app.models.finance import (
        FinancialAccount,
        FinancialCategory,
        FinancialTransaction,
        FinancialTransfer,
    )
    from app.models.loans import Loan
    from app.models.subscriptions import Subscription
    from app.models.user import User


class BillRecurrenceSchedule(Base):
    """
    Recurring bill schedule template generating controlled, idempotent bill occurrences
    (e.g. monthly rent, electricity, quarterly insurance, yearly premium).
    """

    __tablename__ = "bill_recurrence_schedules"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    bill_name: Mapped[str] = mapped_column(String(150), nullable=False)
    bill_category: Mapped[str] = mapped_column(String(40), nullable=False)
    provider_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    account_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    financial_category_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("financial_categories.id", ondelete="SET NULL"),
        nullable=True,
    )
    linked_account_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("financial_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    preferred_payment_method: Mapped[str | None] = mapped_column(String(30), nullable=True)

    frequency: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # weekly, monthly, quarterly, half_yearly, yearly, custom
    custom_interval_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    anchor_day: Mapped[int] = mapped_column(Integer, nullable=False)

    is_variable_amount: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expected_amount: Mapped[Decimal | None] = mapped_column(Numeric(19, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)

    start_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    end_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    next_due_date: Mapped[dt.date] = mapped_column(Date, index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True, nullable=False)

    reminder_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    reminder_days_before: Mapped[list[int]] = mapped_column(
        JSON, default=lambda: [7, 3, 1, 0], nullable=False
    )
    notification_channels: Mapped[dict[str, bool]] = mapped_column(
        JSON, default=lambda: {"in_app": True, "email": False, "sms": False}, nullable=False
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

    user: Mapped["User"] = relationship("User")
    financial_category: Mapped["FinancialCategory | None"] = relationship("FinancialCategory")
    linked_account: Mapped["FinancialAccount | None"] = relationship("FinancialAccount")
    occurrences: Mapped[list["Bill"]] = relationship("Bill", back_populates="schedule")


class Bill(Base):
    """
    Individual bill obligation (either one-time or one occurrence of a recurring schedule).
    Payment state & derived due status (upcoming, due_soon, overdue, paid, partially_paid, archived)
    are evaluated deterministically in the user's configured timezone.
    """

    __tablename__ = "bills"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    parent_schedule_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("bill_recurrence_schedules.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    financial_category_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("financial_categories.id", ondelete="SET NULL"),
        nullable=True,
    )
    linked_account_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("financial_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )

    bill_name: Mapped[str] = mapped_column(String(150), nullable=False)
    bill_category: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    provider_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    account_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    bill_type: Mapped[str] = mapped_column(
        String(20), default="one_time", nullable=False
    )  # one_time, recurring
    frequency: Mapped[str | None] = mapped_column(String(20), nullable=True)

    is_variable_amount: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expected_amount: Mapped[Decimal | None] = mapped_column(Numeric(19, 2), nullable=True)
    current_amount: Mapped[Decimal | None] = mapped_column(Numeric(19, 2), nullable=True)
    amount_paid_total: Mapped[Decimal] = mapped_column(
        Numeric(19, 2), default=Decimal("0.00"), nullable=False
    )
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)

    billing_period_start: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    billing_period_end: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[dt.date] = mapped_column(Date, index=True, nullable=False)
    paid_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    stored_status: Mapped[str] = mapped_column(
        String(20), default="unpaid", index=True, nullable=False
    )  # unpaid, partially_paid, paid, archived
    preferred_payment_method: Mapped[str | None] = mapped_column(String(30), nullable=True)

    reminder_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    reminder_days_before: Mapped[list[int]] = mapped_column(
        JSON, default=lambda: [7, 3, 1, 0], nullable=False
    )
    notification_channels: Mapped[dict[str, bool]] = mapped_column(
        JSON, default=lambda: {"in_app": True, "email": False, "sms": False}, nullable=False
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True, nullable=False)
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
    schedule: Mapped["BillRecurrenceSchedule | None"] = relationship(
        "BillRecurrenceSchedule", back_populates="occurrences"
    )
    financial_category: Mapped["FinancialCategory | None"] = relationship("FinancialCategory")
    linked_account: Mapped["FinancialAccount | None"] = relationship("FinancialAccount")
    payments: Mapped[list["BillPayment"]] = relationship(
        "BillPayment", back_populates="bill", order_by="BillPayment.payment_date.desc()"
    )
    reminders: Mapped[list["BillReminder"]] = relationship(
        "BillReminder", back_populates="bill", cascade="all, delete-orphan"
    )
    documents: Mapped[list["BillDocument"]] = relationship(
        "BillDocument", back_populates="bill", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_bills_user_due_date", "user_id", "due_date"),
        Index("ix_bills_user_active_status", "user_id", "is_active", "stored_status"),
        Index(
            "uq_bills_schedule_due_date",
            "parent_schedule_id",
            "due_date",
            unique=True,
            postgresql_where=text("parent_schedule_id IS NOT NULL"),
        ),
    )


class BillPayment(Base):
    """
    Recorded payment against a bill, auditable and traceable to the authoritative
    FinancialTransaction / FinancialTransfer and double-entry LedgerJournal.
    """

    __tablename__ = "bill_payments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    bill_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("bills.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    financial_account_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("financial_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("financial_transactions.id", ondelete="RESTRICT"),
        unique=True,
        nullable=True,
    )
    transfer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("financial_transfers.id", ondelete="RESTRICT"),
        nullable=True,
    )
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(19, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    payment_date: Mapped[dt.date] = mapped_column(Date, index=True, nullable=False)
    payment_method: Mapped[str] = mapped_column(String(30), default="upi", nullable=False)
    reference_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User")
    bill: Mapped["Bill"] = relationship("Bill", back_populates="payments")
    financial_account: Mapped["FinancialAccount | None"] = relationship("FinancialAccount")
    transaction: Mapped["FinancialTransaction | None"] = relationship("FinancialTransaction")
    transfer: Mapped["FinancialTransfer | None"] = relationship("FinancialTransfer")

    __table_args__ = (
        Index(
            "uq_bill_payments_idempotency",
            "user_id",
            "bill_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )


class BillReminder(Base):
    """
    Durable PostgreSQL-backed scheduled reminder entry with multi-worker safe locking,
    retry tracking, and idempotency key preventing duplicate deliveries across restarts.
    """

    __tablename__ = "bill_reminders"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    bill_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("bills.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("subscriptions.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    loan_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("loans.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    reminder_scope: Mapped[str] = mapped_column(
        String(30), default="bill", index=True, nullable=False
    )  # bill, subscription, loan_emi
    offset_days: Mapped[int] = mapped_column(Integer, nullable=False)
    reminder_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
    channels: Mapped[list[str]] = mapped_column(
        JSON, default=lambda: ["in_app"], nullable=False
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    delivery_status: Mapped[str] = mapped_column(
        String(30), default="pending", index=True, nullable=False
    )  # pending, delivered, partial, unavailable, failed, cancelled
    channel_outcomes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    next_retry_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_attempt_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    delivered_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
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
    bill: Mapped["Bill | None"] = relationship("Bill", back_populates="reminders")
    subscription: Mapped["Subscription | None"] = relationship(
        "Subscription", back_populates="reminders"
    )
    loan: Mapped["Loan | None"] = relationship("Loan", back_populates="reminders")


class BillDocument(Base):
    """Supporting document privately stored for a user's bill (never publicly exposed)."""

    __tablename__ = "bill_documents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    bill_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("bills.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User")
    bill: Mapped["Bill"] = relationship("Bill", back_populates="documents")


class Notification(Base):
    """Persistent user-private in-app notification with deduplication and read tracking."""

    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    notification_type: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    related_bill_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("bills.id", ondelete="SET NULL"),
        nullable=True,
    )
    related_payment_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("bill_payments.id", ondelete="SET NULL"),
        nullable=True,
    )
    related_subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("subscriptions.id", ondelete="SET NULL"),
        nullable=True,
    )
    related_loan_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("loans.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    read_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dedupe_key: Mapped[str | None] = mapped_column(String(120), unique=True, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
        index=True,
        nullable=False,
    )

    user: Mapped["User"] = relationship("User")

    __table_args__ = (
        Index("ix_notifications_user_unread_created", "user_id", "is_read", "created_at"),
    )
