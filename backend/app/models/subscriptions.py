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
    from app.models.bills import BillReminder
    from app.models.finance import (
        FinancialAccount,
        FinancialCategory,
        FinancialTransaction,
        FinancialTransfer,
    )
    from app.models.user import User


class Subscription(Base):
    """
    OTT and recurring SaaS/media/utility subscription managed by a user.
    Amount is nullable so missing prices are never silently coerced to 0.00.
    """

    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    financial_category_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("financial_categories.id", ondelete="SET NULL"), nullable=True
    )
    linked_account_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("financial_accounts.id", ondelete="SET NULL"), nullable=True
    )

    subscription_name: Mapped[str] = mapped_column(String(150), nullable=False)
    provider_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    category: Mapped[str] = mapped_column(
        String(40), default="ott_streaming", index=True, nullable=False
    )
    plan_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    amount: Mapped[Decimal | None] = mapped_column(Numeric(19, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)

    billing_frequency: Mapped[str] = mapped_column(
        String(20), default="monthly", nullable=False
    )  # weekly, monthly, quarterly, half_yearly, yearly, custom
    custom_interval_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    anchor_day: Mapped[int] = mapped_column(Integer, nullable=False)

    start_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    next_renewal_date: Mapped[dt.date | None] = mapped_column(Date, index=True, nullable=True)
    previous_renewal_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    trial_start_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    trial_end_date: Mapped[dt.date | None] = mapped_column(Date, index=True, nullable=True)
    cancellation_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)

    preferred_payment_method: Mapped[str | None] = mapped_column(String(30), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="active", index=True, nullable=False
    )  # active, trial, paused, cancelled, expired, archived

    reminder_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    reminder_days_before: Mapped[list[int]] = mapped_column(
        JSON, default=lambda: [7, 3, 1, 0], nullable=False
    )
    notification_channels: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=lambda: {"in_app": True, "email": False, "sms": False}, nullable=False
    )

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.UTC), nullable=False
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
    price_history: Mapped[list["SubscriptionPriceHistory"]] = relationship(
        "SubscriptionPriceHistory",
        back_populates="subscription",
        cascade="all, delete-orphan",
        order_by="SubscriptionPriceHistory.effective_date.desc()",
    )
    payments: Mapped[list["SubscriptionPayment"]] = relationship(
        "SubscriptionPayment",
        back_populates="subscription",
        cascade="all, delete-orphan",
        order_by="SubscriptionPayment.payment_date.desc()",
    )
    reminders: Mapped[list["BillReminder"]] = relationship(
        "BillReminder",
        back_populates="subscription",
        cascade="all, delete-orphan",
        order_by="BillReminder.reminder_at.asc()",
    )

    __table_args__ = (
        Index("ix_subscriptions_user_status_next", "user_id", "status", "next_renewal_date"),
    )


class SubscriptionPriceHistory(Base):
    """Historical audit trail of subscription plan/price revisions."""

    __tablename__ = "subscription_price_history"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("subscriptions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    previous_price: Mapped[Decimal | None] = mapped_column(Numeric(19, 2), nullable=True)
    new_price: Mapped[Decimal] = mapped_column(Numeric(19, 2), nullable=False)
    effective_date: Mapped[dt.date] = mapped_column(Date, index=True, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.UTC), nullable=False
    )

    user: Mapped["User"] = relationship("User")
    subscription: Mapped["Subscription"] = relationship(
        "Subscription", back_populates="price_history"
    )


class SubscriptionPayment(Base):
    """
    Manual payment or linked transaction recorded against a Subscription.
    Reuses authoritative FinancialTransaction / FinancialTransfer double-entry ledger.
    """

    __tablename__ = "subscription_payments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("subscriptions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    financial_account_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("financial_accounts.id", ondelete="SET NULL"), nullable=True
    )
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("financial_transactions.id", ondelete="RESTRICT"), nullable=True
    )
    transfer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("financial_transfers.id", ondelete="RESTRICT"), nullable=True
    )
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(19, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    payment_date: Mapped[dt.date] = mapped_column(Date, index=True, nullable=False)
    payment_method: Mapped[str] = mapped_column(String(30), default="upi", nullable=False)
    reference_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    payment_status: Mapped[str] = mapped_column(
        String(20), default="completed", nullable=False
    )  # completed, reversed
    reversal_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.UTC), nullable=False
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
        onupdate=lambda: dt.datetime.now(dt.UTC),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User")
    subscription: Mapped["Subscription"] = relationship(
        "Subscription", back_populates="payments"
    )
    financial_account: Mapped["FinancialAccount | None"] = relationship("FinancialAccount")
    transaction: Mapped["FinancialTransaction | None"] = relationship("FinancialTransaction")
    transfer: Mapped["FinancialTransfer | None"] = relationship("FinancialTransfer")

    __table_args__ = (
        Index(
            "uq_sub_payments_idempotency",
            "user_id",
            "subscription_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )


class SubscriptionCandidateDecision(Base):
    """Persisted user review decision (ignored / linked) for deterministic candidate groups."""

    __tablename__ = "subscription_candidate_decisions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    merchant_key: Mapped[str] = mapped_column(String(150), nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)  # ignored, linked
    linked_subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("subscriptions.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.UTC), nullable=False
    )

    user: Mapped["User"] = relationship("User")

    __table_args__ = (
        Index(
            "uq_sub_candidate_user_merchant",
            "user_id",
            "merchant_key",
            unique=True,
        ),
    )
