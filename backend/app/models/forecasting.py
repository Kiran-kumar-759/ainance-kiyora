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
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class FinancialForecast(Base):
    """
    Persisted deterministic financial forecast snapshot scoped strictly per user.
    Forecast records never create or mutate confirmed financial transactions or balances.
    """

    __tablename__ = "financial_forecasts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    forecast_type: Mapped[str] = mapped_column(
        String(40), default="comprehensive", nullable=False
    )
    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    as_of_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    data_cutoff_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    timezone: Mapped[str] = mapped_column(String(50), default="Asia/Kolkata", nullable=False)

    method: Mapped[str] = mapped_column(String(60), nullable=False)
    method_version: Mapped[str] = mapped_column(String(30), default="1.0", nullable=False)
    confidence_label: Mapped[str] = mapped_column(
        String(30), index=True, nullable=False
    )  # high, medium, low, insufficient_data
    confidence_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), default=Decimal("0.0000"), nullable=False
    )

    observation_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    historical_days_covered: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), default="completed", index=True, nullable=False
    )  # completed, insufficient_data, failed
    evaluation_status: Mapped[str] = mapped_column(
        String(30), default="pending_outcome", nullable=False
    )

    assumptions: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    limitations: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    summary_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    input_signature: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)

    generated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.UTC), nullable=False
    )

    values: Mapped[list["ForecastValue"]] = relationship(
        "ForecastValue", back_populates="forecast", cascade="all, delete-orphan"
    )
    explanations: Mapped[list["ForecastExplanation"]] = relationship(
        "ForecastExplanation", back_populates="forecast", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_fin_forecasts_user_horizon_gen", "user_id", "horizon_days", "generated_at"),
    )


class ForecastValue(Base):
    """Normalized series row associated with a persisted FinancialForecast."""

    __tablename__ = "forecast_values"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    forecast_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("financial_forecasts.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    series_type: Mapped[str] = mapped_column(
        String(40), index=True, nullable=False
    )  # cashflow_daily, cashflow_monthly, category, account_balance, commitment, risk, savings
    target_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    reference_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reference_type: Mapped[str | None] = mapped_column(String(40), nullable=True)

    actual_amount: Mapped[Decimal | None] = mapped_column(Numeric(19, 2), nullable=True)
    predicted_amount: Mapped[Decimal | None] = mapped_column(Numeric(19, 2), nullable=True)
    lower_bound: Mapped[Decimal | None] = mapped_column(Numeric(19, 2), nullable=True)
    upper_bound: Mapped[Decimal | None] = mapped_column(Numeric(19, 2), nullable=True)
    baseline_amount: Mapped[Decimal | None] = mapped_column(Numeric(19, 2), nullable=True)
    certainty_label: Mapped[str | None] = mapped_column(String(30), nullable=True)
    is_prediction: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    meta: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    forecast: Mapped["FinancialForecast"] = relationship(
        "FinancialForecast", back_populates="values"
    )


class ForecastExplanation(Base):
    """Evidence-backed explanation linked to a FinancialForecast and supporting financial IDs."""

    __tablename__ = "forecast_explanations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    forecast_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("financial_forecasts.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    explanation_type: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    narrative: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_label: Mapped[str] = mapped_column(String(30), nullable=False)
    supporting_refs: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.UTC), nullable=False
    )

    forecast: Mapped["FinancialForecast"] = relationship(
        "FinancialForecast", back_populates="explanations"
    )


class ForecastScenario(Base):
    """
    Persisted user-explored what-if scenario comparing baseline forecast vs hypothetical adjustments.
    Never modifies real financial transactions, bills, subscriptions, loans, or balances.
    """

    __tablename__ = "forecast_scenarios"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    horizon_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    baseline_summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    scenario_summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    delta_summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.UTC), nullable=False
    )


class ForecastEvaluation(Base):
    """
    Time-aware walk-forward backtest record comparing historical predictions against actuals.
    Strictly prevents future data leakage prior to cutoff_date.
    """

    __tablename__ = "forecast_evaluations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    forecast_type: Mapped[str] = mapped_column(
        String(40), default="comprehensive", nullable=False
    )
    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    cutoff_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    eval_start_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    eval_end_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    method: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), default="evaluated", nullable=False
    )  # evaluated, insufficient_history

    predicted_expense: Mapped[Decimal | None] = mapped_column(Numeric(19, 2), nullable=True)
    actual_expense: Mapped[Decimal | None] = mapped_column(Numeric(19, 2), nullable=True)
    predicted_income: Mapped[Decimal | None] = mapped_column(Numeric(19, 2), nullable=True)
    actual_income: Mapped[Decimal | None] = mapped_column(Numeric(19, 2), nullable=True)
    predicted_net: Mapped[Decimal | None] = mapped_column(Numeric(19, 2), nullable=True)
    actual_net: Mapped[Decimal | None] = mapped_column(Numeric(19, 2), nullable=True)

    mae_expense: Mapped[Decimal | None] = mapped_column(Numeric(19, 2), nullable=True)
    rmse_expense: Mapped[Decimal | None] = mapped_column(Numeric(19, 2), nullable=True)
    wape_expense_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    bias_expense: Mapped[Decimal | None] = mapped_column(Numeric(19, 2), nullable=True)

    category_metrics: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, default=list, nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    evaluated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.UTC), nullable=False
    )

    __table_args__ = (
        Index("ix_forecast_eval_user_date", "user_id", "evaluated_at"),
    )
