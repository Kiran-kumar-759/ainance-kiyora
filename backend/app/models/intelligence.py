import datetime as dt
import uuid
from decimal import Decimal
from typing import Any

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
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class MerchantIdentity(Base):
    """Normalized merchant entity isolated per user with aggregate spend tracking."""

    __tablename__ = "merchant_identities"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    canonical_key: Mapped[str] = mapped_column(String(120), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(150), nullable=False)
    default_category_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("financial_categories.id", ondelete="SET NULL"), nullable=True
    )
    default_category_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_user_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    transaction_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_spent: Mapped[Decimal] = mapped_column(
        Numeric(19, 2), default=Decimal("0.00"), nullable=False
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

    aliases: Mapped[list["MerchantAlias"]] = relationship(
        "MerchantAlias", back_populates="merchant", cascade="all, delete-orphan"
    )
    category_mapping: Mapped["MerchantCategoryMapping | None"] = relationship(
        "MerchantCategoryMapping",
        back_populates="merchant",
        uselist=False,
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("user_id", "canonical_key", name="uq_merchant_user_canonical_key"),
    )


class MerchantAlias(Base):
    """Raw bank/UPI merchant strings mapped to a canonical MerchantIdentity."""

    __tablename__ = "merchant_aliases"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("merchant_identities.id", ondelete="CASCADE"), index=True, nullable=False
    )
    raw_pattern: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_token: Mapped[str] = mapped_column(String(150), nullable=False)
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.UTC), nullable=False
    )

    merchant: Mapped["MerchantIdentity"] = relationship("MerchantIdentity", back_populates="aliases")

    __table_args__ = (
        UniqueConstraint("user_id", "raw_pattern", name="uq_merchant_alias_user_pattern"),
    )


class MerchantCategoryMapping(Base):
    """Learned or user-confirmed mapping between a normalized merchant and a category."""

    __tablename__ = "merchant_category_mappings"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("merchant_identities.id", ondelete="CASCADE"), index=True, nullable=False
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("financial_categories.id", ondelete="CASCADE"), nullable=False
    )
    category_name: Mapped[str] = mapped_column(String(100), nullable=False)
    source: Mapped[str] = mapped_column(
        String(30), default="user_confirmed", nullable=False
    )  # user_confirmed, rule, ai_suggested
    confidence: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), default=Decimal("1.0000"), nullable=False
    )
    is_authoritative: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.UTC), nullable=False
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
        onupdate=lambda: dt.datetime.now(dt.UTC),
        nullable=False,
    )

    merchant: Mapped["MerchantIdentity"] = relationship(
        "MerchantIdentity", back_populates="category_mapping"
    )

    __table_args__ = (
        UniqueConstraint("user_id", "merchant_id", name="uq_merch_cat_map_user_merchant"),
    )


class TransactionCategorization(Base):
    """
    Explainable AI & rule categorization record linked 1:1 with a FinancialTransaction.
    Preserves original descriptions and authoritative user overrides cleanly.
    """

    __tablename__ = "transaction_categorizations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("financial_transactions.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    merchant_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("merchant_identities.id", ondelete="SET NULL"), index=True, nullable=True
    )

    current_category_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("financial_categories.id", ondelete="SET NULL"), nullable=True
    )
    current_category_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    suggested_category_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("financial_categories.id", ondelete="SET NULL"), nullable=True
    )
    suggested_category_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    predicted_category_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    classification_method: Mapped[str] = mapped_column(
        String(40), nullable=False
    )  # user_override, confirmed_mapping, deterministic_rule, ml_classifier, groq_llm, needs_review
    confidence: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), default=Decimal("0.0000"), nullable=False
    )
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(60), nullable=True)
    provider_name: Mapped[str | None] = mapped_column(String(40), nullable=True)
    review_status: Mapped[str] = mapped_column(
        String(30), default="needs_review", index=True, nullable=False
    )  # auto_applied, needs_review, accepted, overridden, rejected
    input_signature: Mapped[str | None] = mapped_column(String(64), nullable=True)

    analyzed_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.UTC), nullable=False
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
        onupdate=lambda: dt.datetime.now(dt.UTC),
        nullable=False,
    )

    merchant: Mapped["MerchantIdentity | None"] = relationship("MerchantIdentity")

    __table_args__ = (
        Index("ix_tx_cat_user_review_status", "user_id", "review_status"),
    )


class CategorizationFeedback(Base):
    """Audit trail of user category and merchant corrections (user-scoped)."""

    __tablename__ = "categorization_feedback"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("financial_transactions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    categorization_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("transaction_categorizations.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # accepted, changed, rejected, merchant_corrected
    previous_category_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    previous_category_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    new_category_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    new_category_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    previous_merchant_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    new_merchant_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.UTC), nullable=False
    )


class AiModelMetadata(Base):
    """
    Strictly isolated per-user ML classifier state & real evaluation metrics.
    One user's financial history never trains models exposed to another user.
    """

    __tablename__ = "ai_model_metadata"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    model_name: Mapped[str] = mapped_column(String(60), default="tfidf_logreg_v1", nullable=False)
    model_version: Mapped[str] = mapped_column(String(40), default="1.0", nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), default="insufficient_data", nullable=False
    )  # ready, insufficient_data, failed
    training_sample_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    class_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    accuracy: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    precision_weighted: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    recall_weighted: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    f1_weighted: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    confusion_matrix: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    evaluation_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    serialized_pipeline_b64: Mapped[str | None] = mapped_column(Text, nullable=True)
    trained_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
        onupdate=lambda: dt.datetime.now(dt.UTC),
        nullable=False,
    )


class RecurringPaymentCandidate(Base):
    """
    Unified Phase 8 recurring payment candidate supporting fixed & variable amounts
    and integrating cleanly with Phase 6 Subscription & SubscriptionCandidateDecision.
    """

    __tablename__ = "recurring_payment_candidates"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    merchant_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("merchant_identities.id", ondelete="SET NULL"), nullable=True
    )
    merchant_key: Mapped[str] = mapped_column(String(120), nullable=False)
    merchant_name: Mapped[str] = mapped_column(String(150), nullable=False)
    suggested_category_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    commitment_type: Mapped[str] = mapped_column(
        String(30), default="recurring_expense", nullable=False
    )  # subscription_candidate, recurring_utility, recurring_expense, confirmed_subscription
    frequency: Mapped[str] = mapped_column(String(20), nullable=False)
    estimated_amount: Mapped[Decimal] = mapped_column(Numeric(19, 2), nullable=False)
    min_amount: Mapped[Decimal] = mapped_column(Numeric(19, 2), nullable=False)
    max_amount: Mapped[Decimal] = mapped_column(Numeric(19, 2), nullable=False)
    amount_variability_pct: Mapped[Decimal] = mapped_column(
        Numeric(6, 2), default=Decimal("0.00"), nullable=False
    )
    is_variable_amount: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    occurrence_count: Mapped[int] = mapped_column(Integer, nullable=False)
    first_seen_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    last_seen_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    next_expected_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    detection_method: Mapped[str] = mapped_column(
        String(40), default="deterministic_interval", nullable=False
    )
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    review_status: Mapped[str] = mapped_column(
        String(30), default="pending_review", index=True, nullable=False
    )  # pending_review, confirmed, rejected, linked_subscription
    linked_subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("subscriptions.id", ondelete="SET NULL"), nullable=True
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

    __table_args__ = (
        UniqueConstraint("user_id", "merchant_key", "frequency", name="uq_recur_cand_user_key_freq"),
    )


class SpendingAnomaly(Base):
    """
    Explainable statistical unusual-spending detection record.
    Never labels transactions as fraudulent or unauthorized.
    """

    __tablename__ = "spending_anomalies"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("financial_transactions.id", ondelete="CASCADE"), index=True, nullable=True
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("financial_categories.id", ondelete="SET NULL"), nullable=True
    )
    category_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    merchant_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    anomaly_type: Mapped[str] = mapped_column(
        String(40), nullable=False
    )  # merchant_spike, category_spike, recurring_amount_jump
    observed_amount: Mapped[Decimal] = mapped_column(Numeric(19, 2), nullable=False)
    baseline_amount: Mapped[Decimal] = mapped_column(Numeric(19, 2), nullable=False)
    deviation_pct: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)  # low, medium, high
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    detection_method: Mapped[str] = mapped_column(String(50), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    supporting_transaction_ids: Mapped[list[str]] = mapped_column(
        JSON, default=list, nullable=False
    )
    dedupe_key: Mapped[str] = mapped_column(String(160), nullable=False)
    review_status: Mapped[str] = mapped_column(
        String(30), default="new", index=True, nullable=False
    )  # new, acknowledged, dismissed
    detected_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.UTC), nullable=False
    )
    reviewed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (UniqueConstraint("user_id", "dedupe_key", name="uq_anomaly_user_dedupe"),)


class FinancialInsight(Base):
    """Deduplicated, evidence-backed financial observation grounded in PostgreSQL data."""

    __tablename__ = "financial_insights"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    insight_type: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="info", nullable=False)
    period_start: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    supporting_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    calculation_method: Mapped[str] = mapped_column(String(60), nullable=False)
    provider_name: Mapped[str | None] = mapped_column(String(40), nullable=True)
    confidence: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), default=Decimal("0.9000"), nullable=False
    )
    suggested_action: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dedupe_key: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="new", index=True, nullable=False
    )  # new, read, dismissed
    generated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.UTC), nullable=False
    )
    read_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dismissed_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (UniqueConstraint("user_id", "dedupe_key", name="uq_insight_user_dedupe"),)


class AiProcessingJob(Base):
    """Durable background job & provider execution audit record without storing credentials."""

    __tablename__ = "ai_processing_jobs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    job_type: Mapped[str] = mapped_column(
        String(40), default="full_intelligence_run", nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(30), default="queued", index=True, nullable=False
    )  # queued, processing, completed, failed
    provider_name: Mapped[str | None] = mapped_column(String(40), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(60), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(30), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    items_processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.UTC), nullable=False
    )

    __table_args__ = (
        Index(
            "uq_ai_active_job_per_user",
            "user_id",
            "job_type",
            unique=True,
            postgresql_where=text("status IN ('queued', 'processing')"),
        ),
    )
