import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.auth import (
        EmailVerificationToken,
        PasswordResetToken,
        UserPreference,
        UserSession,
    )
    from app.models.finance import (
        BankingConnection,
        FinancialAccount,
        FinancialCategory,
        FinancialTransaction,
        FinancialTransfer,
        LedgerJournal,
    )


class User(Base):
    """Core user identity model representing individual SaaS accounts."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    sessions: Mapped[list["UserSession"]] = relationship(
        "UserSession",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    preferences: Mapped["UserPreference | None"] = relationship(
        "UserPreference",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    verification_tokens: Mapped[list["EmailVerificationToken"]] = relationship(
        "EmailVerificationToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    reset_tokens: Mapped[list["PasswordResetToken"]] = relationship(
        "PasswordResetToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    accounts: Mapped[list["FinancialAccount"]] = relationship(
        "FinancialAccount",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    categories: Mapped[list["FinancialCategory"]] = relationship(
        "FinancialCategory",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    transactions: Mapped[list["FinancialTransaction"]] = relationship(
        "FinancialTransaction",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    transfers: Mapped[list["FinancialTransfer"]] = relationship(
        "FinancialTransfer",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    journals: Mapped[list["LedgerJournal"]] = relationship(
        "LedgerJournal",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    banking_connections: Mapped[list["BankingConnection"]] = relationship(
        "BankingConnection",
        back_populates="user",
        cascade="all, delete-orphan",
    )
