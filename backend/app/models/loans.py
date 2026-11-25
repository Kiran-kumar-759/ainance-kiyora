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
        FinancialTransaction,
        FinancialTransfer,
    )
    from app.models.user import User


class Loan(Base):
    """
    Loan entity backed by an authoritative FinancialAccount (account_type='loan_liability')
    so outstanding principal participates directly in double-entry ledger & net worth calculations.
    """

    __tablename__ = "loans"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    liability_account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("financial_accounts.id", ondelete="RESTRICT"), nullable=False
    )
    linked_repayment_account_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("financial_accounts.id", ondelete="SET NULL"), nullable=True
    )

    loan_name: Mapped[str] = mapped_column(String(150), nullable=False)
    lender_name: Mapped[str] = mapped_column(String(150), nullable=False)
    loan_type: Mapped[str] = mapped_column(
        String(30), default="personal", index=True, nullable=False
    )  # personal, education, home, vehicle, gold, business, consumer_durable, other

    original_principal: Mapped[Decimal | None] = mapped_column(Numeric(19, 2), nullable=True)
    outstanding_principal_at_start: Mapped[Decimal] = mapped_column(
        Numeric(19, 2), nullable=False
    )
    current_outstanding_principal: Mapped[Decimal] = mapped_column(
        Numeric(19, 2), nullable=False
    )
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)

    interest_rate: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    interest_rate_type: Mapped[str] = mapped_column(
        String(20), default="fixed", nullable=False
    )  # fixed, floating
    calculation_method: Mapped[str] = mapped_column(
        String(30), default="reducing_balance", nullable=False
    )  # reducing_balance, flat_rate, zero_interest

    loan_start_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    tracking_start_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    first_emi_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    next_emi_due_date: Mapped[dt.date | None] = mapped_column(Date, index=True, nullable=True)
    maturity_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)

    original_tenure_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    remaining_tenure_months: Mapped[int] = mapped_column(Integer, nullable=False)
    emi_amount: Mapped[Decimal] = mapped_column(Numeric(19, 2), nullable=False)
    emi_frequency: Mapped[str] = mapped_column(
        String(20), default="monthly", nullable=False
    )  # monthly, quarterly, weekly
    anchor_day: Mapped[int] = mapped_column(Integer, nullable=False)

    loan_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    processing_fee: Mapped[Decimal | None] = mapped_column(Numeric(19, 2), nullable=True)
    prepayment_charges_info: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="active", index=True, nullable=False
    )  # active, closed, overdue, paused, archived

    reminder_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    reminder_days_before: Mapped[list[int]] = mapped_column(
        JSON, default=lambda: [5, 3, 1, 0], nullable=False
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
    liability_account: Mapped["FinancialAccount"] = relationship(
        "FinancialAccount", foreign_keys=[liability_account_id]
    )
    linked_repayment_account: Mapped["FinancialAccount | None"] = relationship(
        "FinancialAccount", foreign_keys=[linked_repayment_account_id]
    )
    installments: Mapped[list["LoanInstallment"]] = relationship(
        "LoanInstallment",
        back_populates="loan",
        cascade="all, delete-orphan",
        order_by="LoanInstallment.installment_number.asc()",
    )
    rate_history: Mapped[list["LoanInterestRateHistory"]] = relationship(
        "LoanInterestRateHistory",
        back_populates="loan",
        cascade="all, delete-orphan",
        order_by="LoanInterestRateHistory.effective_date.desc()",
    )
    payments: Mapped[list["LoanPayment"]] = relationship(
        "LoanPayment",
        back_populates="loan",
        cascade="all, delete-orphan",
        order_by="LoanPayment.payment_date.desc()",
    )
    reminders: Mapped[list["BillReminder"]] = relationship(
        "BillReminder",
        back_populates="loan",
        cascade="all, delete-orphan",
        order_by="BillReminder.reminder_at.asc()",
    )

    __table_args__ = (Index("ix_loans_user_status_next", "user_id", "status", "next_emi_due_date"),)


class LoanInstallment(Base):
    """Persisted amortization installment schedule preserving completed rows across revisions."""

    __tablename__ = "loan_installments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    loan_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("loans.id", ondelete="CASCADE"), index=True, nullable=False
    )
    installment_number: Mapped[int] = mapped_column(Integer, nullable=False)
    due_date: Mapped[dt.date] = mapped_column(Date, index=True, nullable=False)
    opening_principal: Mapped[Decimal] = mapped_column(Numeric(19, 2), nullable=False)
    emi_amount: Mapped[Decimal] = mapped_column(Numeric(19, 2), nullable=False)
    principal_component: Mapped[Decimal] = mapped_column(Numeric(19, 2), nullable=False)
    interest_component: Mapped[Decimal] = mapped_column(Numeric(19, 2), nullable=False)
    closing_principal: Mapped[Decimal] = mapped_column(Numeric(19, 2), nullable=False)
    principal_paid: Mapped[Decimal] = mapped_column(
        Numeric(19, 2), default=Decimal("0.00"), nullable=False
    )
    interest_paid: Mapped[Decimal] = mapped_column(
        Numeric(19, 2), default=Decimal("0.00"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), default="upcoming", index=True, nullable=False
    )  # upcoming, partially_paid, paid, cancelled
    paid_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    is_final_adjustment: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.UTC), nullable=False
    )

    loan: Mapped["Loan"] = relationship("Loan", back_populates="installments")

    __table_args__ = (
        Index(
            "uq_loan_installment_active_num",
            "loan_id",
            "installment_number",
            unique=True,
            postgresql_where=text("status != 'cancelled'"),
        ),
    )


class LoanInterestRateHistory(Base):
    """Audit trail of floating/fixed interest rate revisions on a loan."""

    __tablename__ = "loan_interest_rate_history"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    loan_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("loans.id", ondelete="CASCADE"), index=True, nullable=False
    )
    previous_rate: Mapped[Decimal | None] = mapped_column(Numeric(6, 3), nullable=True)
    new_rate: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    effective_date: Mapped[dt.date] = mapped_column(Date, index=True, nullable=False)
    previous_emi: Mapped[Decimal | None] = mapped_column(Numeric(19, 2), nullable=True)
    new_emi: Mapped[Decimal] = mapped_column(Numeric(19, 2), nullable=False)
    remaining_tenure_months: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.UTC), nullable=False
    )

    loan: Mapped["Loan"] = relationship("Loan", back_populates="rate_history")


class LoanPayment(Base):
    """
    Loan repayment record splitting Principal Repayment (transfer reducing loan liability)
    and Interest Expense (expense transaction recorded in double-entry ledger & analytics).
    """

    __tablename__ = "loan_payments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    loan_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("loans.id", ondelete="CASCADE"), index=True, nullable=False
    )
    installment_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("loan_installments.id", ondelete="SET NULL"), nullable=True
    )
    payment_account_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("financial_accounts.id", ondelete="SET NULL"), nullable=True
    )
    principal_transfer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("financial_transfers.id", ondelete="RESTRICT"), nullable=True
    )
    interest_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("financial_transactions.id", ondelete="RESTRICT"), nullable=True
    )
    fee_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("financial_transactions.id", ondelete="RESTRICT"), nullable=True
    )
    linked_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("financial_transactions.id", ondelete="RESTRICT"), nullable=True
    )

    payment_type: Mapped[str] = mapped_column(
        String(25), default="emi", nullable=False
    )  # emi, partial, prepayment, foreclosure, linked_transaction
    payment_date: Mapped[dt.date] = mapped_column(Date, index=True, nullable=False)
    principal_paid: Mapped[Decimal] = mapped_column(Numeric(19, 2), nullable=False)
    interest_paid: Mapped[Decimal] = mapped_column(
        Numeric(19, 2), default=Decimal("0.00"), nullable=False
    )
    fee_paid: Mapped[Decimal] = mapped_column(
        Numeric(19, 2), default=Decimal("0.00"), nullable=False
    )
    total_paid: Mapped[Decimal] = mapped_column(Numeric(19, 2), nullable=False)

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
    loan: Mapped["Loan"] = relationship("Loan", back_populates="payments")
    installment: Mapped["LoanInstallment | None"] = relationship("LoanInstallment")
    payment_account: Mapped["FinancialAccount | None"] = relationship("FinancialAccount")
    principal_transfer: Mapped["FinancialTransfer | None"] = relationship(
        "FinancialTransfer", foreign_keys=[principal_transfer_id]
    )
    interest_transaction: Mapped["FinancialTransaction | None"] = relationship(
        "FinancialTransaction", foreign_keys=[interest_transaction_id]
    )
    fee_transaction: Mapped["FinancialTransaction | None"] = relationship(
        "FinancialTransaction", foreign_keys=[fee_transaction_id]
    )
    linked_transaction: Mapped["FinancialTransaction | None"] = relationship(
        "FinancialTransaction", foreign_keys=[linked_transaction_id]
    )

    __table_args__ = (
        Index(
            "uq_loan_payments_idempotency",
            "user_id",
            "loan_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )
