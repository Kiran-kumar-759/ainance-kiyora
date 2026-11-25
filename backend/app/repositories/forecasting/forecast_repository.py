import datetime as dt
import uuid

from sqlalchemy import and_, desc, exists, not_, select
from sqlalchemy.orm import Session, selectinload

from app.models.auth import UserPreference
from app.models.bills import Bill, BillRecurrenceSchedule
from app.models.finance import (
    FinancialAccount,
    FinancialTransaction,
    LedgerJournal,
)
from app.models.forecasting import (
    FinancialForecast,
    ForecastEvaluation,
    ForecastScenario,
)
from app.models.intelligence import (
    AiProcessingJob,
    RecurringPaymentCandidate,
    SpendingAnomaly,
    TransactionCategorization,
)
from app.models.loans import Loan, LoanInstallment
from app.models.subscriptions import Subscription


class ForecastRepository:
    """PostgreSQL repository for Phase 9 Financial Forecasting & Predictive Analytics."""

    @staticmethod
    def _active_journal_clause():
        has_reversed = exists(
            select(LedgerJournal.id).where(
                LedgerJournal.transaction_id == FinancialTransaction.id,
                LedgerJournal.is_reversed.is_(True),
            )
        )
        has_active = exists(
            select(LedgerJournal.id).where(
                LedgerJournal.transaction_id == FinancialTransaction.id,
                LedgerJournal.is_reversed.is_(False),
            )
        )
        return not_(and_(has_reversed, not_(has_active)))

    def get_user_timezone(self, db: Session, user_id: uuid.UUID) -> str:
        pref = db.execute(
            select(UserPreference).where(UserPreference.user_id == user_id)
        ).scalar_one_or_none()
        return (pref.timezone if pref and pref.timezone else None) or "Asia/Kolkata"

    def list_eligible_transactions(
        self,
        db: Session,
        user_id: uuid.UUID,
        *,
        date_from: dt.date | None = None,
        date_to: dt.date | None = None,
    ) -> list[FinancialTransaction]:
        """
        Return active, non-transfer income/expense transactions strictly up to date_to,
        excluding disconnected accounts and reversed ledger journals.
        """
        stmt = (
            select(FinancialTransaction)
            .join(FinancialAccount, FinancialTransaction.account_id == FinancialAccount.id)
            .options(selectinload(FinancialTransaction.category))
            .where(
                FinancialTransaction.user_id == user_id,
                FinancialTransaction.transfer_id.is_(None),
                FinancialTransaction.transaction_type.in_(["income", "expense"]),
                FinancialAccount.status != "disconnected",
                self._active_journal_clause(),
            )
            .order_by(FinancialTransaction.transaction_date.asc(), FinancialTransaction.created_at.asc())
        )
        if date_from:
            stmt = stmt.where(FinancialTransaction.transaction_date >= date_from)
        if date_to:
            stmt = stmt.where(FinancialTransaction.transaction_date <= date_to)
        return list(db.execute(stmt).scalars().all())

    def list_active_accounts(self, db: Session, user_id: uuid.UUID) -> list[FinancialAccount]:
        stmt = (
            select(FinancialAccount)
            .where(
                FinancialAccount.user_id == user_id,
                FinancialAccount.status == "active",
            )
            .order_by(FinancialAccount.account_type.asc(), FinancialAccount.name.asc())
        )
        return list(db.execute(stmt).scalars().all())

    def list_categorizations_map(
        self, db: Session, user_id: uuid.UUID
    ) -> dict[uuid.UUID, TransactionCategorization]:
        rows = db.execute(
            select(TransactionCategorization).where(TransactionCategorization.user_id == user_id)
        ).scalars().all()
        return {r.transaction_id: r for r in rows}

    def list_open_bills(
        self, db: Session, user_id: uuid.UUID, *, cutoff_end: dt.date
    ) -> list[Bill]:
        stmt = (
            select(Bill)
            .options(selectinload(Bill.financial_category), selectinload(Bill.linked_account))
            .where(
                Bill.user_id == user_id,
                Bill.is_active.is_(True),
                Bill.stored_status.in_(["unpaid", "partially_paid"]),
                Bill.due_date <= cutoff_end,
            )
            .order_by(Bill.due_date.asc())
        )
        return list(db.execute(stmt).scalars().all())

    def list_active_bill_schedules(
        self, db: Session, user_id: uuid.UUID
    ) -> list[BillRecurrenceSchedule]:
        stmt = (
            select(BillRecurrenceSchedule)
            .where(
                BillRecurrenceSchedule.user_id == user_id,
                BillRecurrenceSchedule.is_active.is_(True),
            )
            .order_by(BillRecurrenceSchedule.next_due_date.asc())
        )
        return list(db.execute(stmt).scalars().all())

    def list_active_subscriptions(self, db: Session, user_id: uuid.UUID) -> list[Subscription]:
        stmt = (
            select(Subscription)
            .where(
                Subscription.user_id == user_id,
                Subscription.status.in_(["active", "trial"]),
            )
            .order_by(Subscription.next_renewal_date.asc())
        )
        return list(db.execute(stmt).scalars().all())

    def list_active_loans_with_installments(
        self, db: Session, user_id: uuid.UUID, *, cutoff_end: dt.date
    ) -> list[tuple[Loan, list[LoanInstallment]]]:
        loans = list(
            db.execute(
                select(Loan)
                .where(
                    Loan.user_id == user_id,
                    Loan.status.in_(["active", "overdue"]),
                )
                .order_by(Loan.next_emi_due_date.asc())
            )
            .scalars()
            .all()
        )
        out: list[tuple[Loan, list[LoanInstallment]]] = []
        for loan in loans:
            insts = list(
                db.execute(
                    select(LoanInstallment)
                    .where(
                        LoanInstallment.loan_id == loan.id,
                        LoanInstallment.user_id == user_id,
                        LoanInstallment.status.in_(["upcoming", "partially_paid"]),
                        LoanInstallment.due_date <= cutoff_end,
                    )
                    .order_by(LoanInstallment.due_date.asc())
                )
                .scalars()
                .all()
            )
            out.append((loan, insts))
        return out

    def list_pending_recurring_candidates(
        self, db: Session, user_id: uuid.UUID
    ) -> list[RecurringPaymentCandidate]:
        stmt = select(RecurringPaymentCandidate).where(
            RecurringPaymentCandidate.user_id == user_id,
            RecurringPaymentCandidate.review_status == "pending",
        )
        return list(db.execute(stmt).scalars().all())

    def list_recent_anomalies(
        self, db: Session, user_id: uuid.UUID, *, limit: int = 10
    ) -> list[SpendingAnomaly]:
        stmt = (
            select(SpendingAnomaly)
            .where(
                SpendingAnomaly.user_id == user_id,
                SpendingAnomaly.review_status != "dismissed",
            )
            .order_by(desc(SpendingAnomaly.detected_at))
            .limit(limit)
        )
        return list(db.execute(stmt).scalars().all())

    # ── Forecast persistence ──────────────────────────────────────────────────

    def get_latest_forecast(
        self, db: Session, user_id: uuid.UUID, *, horizon_days: int
    ) -> FinancialForecast | None:
        stmt = (
            select(FinancialForecast)
            .options(
                selectinload(FinancialForecast.values),
                selectinload(FinancialForecast.explanations),
            )
            .where(
                FinancialForecast.user_id == user_id,
                FinancialForecast.horizon_days == horizon_days,
            )
            .order_by(desc(FinancialForecast.generated_at))
            .limit(1)
        )
        return db.execute(stmt).scalar_one_or_none()

    def get_forecast_by_id(
        self, db: Session, user_id: uuid.UUID, forecast_id: uuid.UUID
    ) -> FinancialForecast | None:
        stmt = (
            select(FinancialForecast)
            .options(
                selectinload(FinancialForecast.values),
                selectinload(FinancialForecast.explanations),
            )
            .where(
                FinancialForecast.id == forecast_id,
                FinancialForecast.user_id == user_id,
            )
        )
        return db.execute(stmt).scalar_one_or_none()

    def list_forecast_history(
        self,
        db: Session,
        user_id: uuid.UUID,
        *,
        horizon_days: int | None = None,
        limit: int = 25,
    ) -> list[FinancialForecast]:
        stmt = select(FinancialForecast).where(FinancialForecast.user_id == user_id)
        if horizon_days is not None:
            stmt = stmt.where(FinancialForecast.horizon_days == horizon_days)
        stmt = stmt.order_by(desc(FinancialForecast.generated_at)).limit(limit)
        return list(db.execute(stmt).scalars().all())

    # ── Scenarios & Evaluations ───────────────────────────────────────────────

    def list_scenarios(
        self, db: Session, user_id: uuid.UUID, *, limit: int = 30
    ) -> list[ForecastScenario]:
        stmt = (
            select(ForecastScenario)
            .where(ForecastScenario.user_id == user_id)
            .order_by(desc(ForecastScenario.created_at))
            .limit(limit)
        )
        return list(db.execute(stmt).scalars().all())

    def get_scenario_by_id(
        self, db: Session, user_id: uuid.UUID, scenario_id: uuid.UUID
    ) -> ForecastScenario | None:
        stmt = select(ForecastScenario).where(
            ForecastScenario.id == scenario_id,
            ForecastScenario.user_id == user_id,
        )
        return db.execute(stmt).scalar_one_or_none()

    def list_evaluations(
        self, db: Session, user_id: uuid.UUID, *, limit: int = 20
    ) -> list[ForecastEvaluation]:
        stmt = (
            select(ForecastEvaluation)
            .where(ForecastEvaluation.user_id == user_id)
            .order_by(desc(ForecastEvaluation.evaluated_at))
            .limit(limit)
        )
        return list(db.execute(stmt).scalars().all())

    def get_active_forecast_job(
        self, db: Session, user_id: uuid.UUID
    ) -> AiProcessingJob | None:
        stmt = (
            select(AiProcessingJob)
            .where(
                AiProcessingJob.user_id == user_id,
                AiProcessingJob.job_type == "forecast_generation",
                AiProcessingJob.status.in_(["queued", "processing"]),
            )
            .order_by(desc(AiProcessingJob.created_at))
            .limit(1)
        )
        return db.execute(stmt).scalar_one_or_none()
