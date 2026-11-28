import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class UserOnboardingState(Base):
    """
    Persistent PostgreSQL state machine for first-time user onboarding,
    financial-data setup selection, and idempotent workspace initialization.
    """

    __tablename__ = "user_onboarding_states"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    current_stage: Mapped[str] = mapped_column(
        String(40),
        default="registered",
        nullable=False,
    )  # registered, profile_setup, financial_data_setup, data_processing, skipped, completed
    completed_stages: Mapped[list[str]] = mapped_column(
        JSON,
        default=lambda: ["registered"],
        nullable=False,
    )
    current_step: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    profile_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    financial_setup_status: Mapped[str] = mapped_column(
        String(40),
        default="not_started",
        nullable=False,
    )  # not_started, selected, in_progress, connected, manual_added, imported, documents_uploaded, skipped, completed
    selected_setup_method: Mapped[str | None] = mapped_column(
        String(40),
        nullable=True,
    )  # bank_connect, manual_account, statement_import, document_upload, skip
    financial_setup_skipped: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    financial_profile: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    initialization_status: Mapped[str] = mapped_column(
        String(30),
        default="not_started",
        nullable=False,
    )  # not_started, in_progress, completed, failed
    initialization_steps: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    initialization_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    initialization_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    initialization_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
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

    user: Mapped["User"] = relationship("User", back_populates="onboarding_state")
