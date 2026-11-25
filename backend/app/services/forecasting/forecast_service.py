import datetime as dt
import hashlib
import uuid
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.bills import Bill
from app.models.finance import FinancialAccount, FinancialTransaction
from app.models.forecasting import FinancialForecast, ForecastScenario, ForecastValue
from app.models.intelligence import AiProcessingJob
from app.models.loans import Loan
from app.models.subscriptions import Subscription
from app.models.user import User
from app.repositories.forecasting.forecast_repository import ForecastRepository
from app.schemas.forecasting import (
    AccountBalanceForecastItem,
    CashflowForecastResponse,
    CategoryForecastItem,
    CommitmentForecastItem,
    ExpenseForecastResponse,
    ForecastEvaluationResponse,
    ForecastExplanationItem,
    ForecastingOverviewResponse,
    ForecastRecordResponse,
    ForecastScenarioOutcome,
    ForecastScenarioRequest,
    ForecastScenarioResponse,
    GenerateForecastRequest,
    IncomeForecastResponse,
    RiskWarningItem,
    SavingsForecastResponse,
)
from app.services.bills.status_engine import resolve_user_today
from app.services.forecasting.cashflow_balance_forecaster import build_cashflow_and_balances
from app.services.forecasting.commitment_forecaster import collect_upcoming_commitments
from app.services.forecasting.expense_income_forecaster import (
    forecast_categories,
    forecast_expenses,
    forecast_income,
)
from app.services.forecasting.forecast_evaluation import run_time_aware_backtest
from app.services.forecasting.forecast_explanations import build_forecast_explanations
from app.services.forecasting.risk_savings_scenario_forecaster import (
    compute_savings_projection,
    detect_financial_risks,
    evaluate_what_if_scenario,
)


class ForecastService:
    """Orchestrator service for Phase 9 Financial Forecasting & Predictive Analytics."""

    def __init__(self):
        self.repo = ForecastRepository()

    def _compute_input_signature(
        self,
        db: Session,
        user_id: uuid.UUID,
        *,
        as_of_date: dt.date,
        horizon_days: int,
        low_balance_threshold: Decimal,
    ) -> str:
        tx_stats = db.execute(
            select(func.count(FinancialTransaction.id), func.max(FinancialTransaction.updated_at)).where(
                FinancialTransaction.user_id == user_id
            )
        ).one()
        acc_max = db.execute(
            select(func.count(FinancialAccount.id), func.max(FinancialAccount.updated_at)).where(
                FinancialAccount.user_id == user_id
            )
        ).one()
        bill_max = db.execute(
            select(func.count(Bill.id), func.max(Bill.updated_at)).where(Bill.user_id == user_id)
        ).one()
        sub_max = db.execute(
            select(func.count(Subscription.id), func.max(Subscription.updated_at)).where(
                Subscription.user_id == user_id
            )
        ).one()
        loan_max = db.execute(
            select(func.count(Loan.id), func.max(Loan.updated_at)).where(Loan.user_id == user_id)
        ).one()

        raw = "|".join(
            [
                str(user_id),
                as_of_date.isoformat(),
                str(horizon_days),
                str(low_balance_threshold),
                str(tx_stats[0]),
                str(tx_stats[1]),
                str(acc_max[0]),
                str(acc_max[1]),
                str(bill_max[0]),
                str(bill_max[1]),
                str(sub_max[0]),
                str(sub_max[1]),
                str(loan_max[0]),
                str(loan_max[1]),
            ]
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _serialize_overview(
        self,
        forecast: FinancialForecast,
        *,
        is_stale: bool = False,
    ) -> ForecastingOverviewResponse:
        p = forecast.summary_payload or {}
        return ForecastingOverviewResponse(
            forecast=ForecastRecordResponse.model_validate(forecast),
            cashflow=CashflowForecastResponse.model_validate(p["cashflow"]),
            expenses=ExpenseForecastResponse.model_validate(p["expenses"]),
            income=IncomeForecastResponse.model_validate(p["income"]),
            categories=[CategoryForecastItem.model_validate(c) for c in p.get("categories", [])],
            commitments=[CommitmentForecastItem.model_validate(c) for c in p.get("commitments", [])],
            balances=[AccountBalanceForecastItem.model_validate(b) for b in p.get("balances", [])],
            risks=[RiskWarningItem.model_validate(r) for r in p.get("risks", [])],
            savings=SavingsForecastResponse.model_validate(p["savings"]),
            explanations=[
                ForecastExplanationItem.model_validate(e) for e in forecast.explanations
            ],
            is_stale=is_stale,
        )

    def generate_forecast_for_user(
        self,
        db: Session,
        user_id: uuid.UUID,
        req: GenerateForecastRequest,
        *,
        existing_job: AiProcessingJob | None = None,
    ) -> ForecastingOverviewResponse:
        tz = self.repo.get_user_timezone(db, user_id)
        as_of_date = resolve_user_today(tz)
        sig = self._compute_input_signature(
            db,
            user_id,
            as_of_date=as_of_date,
            horizon_days=req.horizon_days,
            low_balance_threshold=req.low_balance_threshold,
        )

        if not req.force_refresh:
            cached = self.repo.get_latest_forecast(db, user_id, horizon_days=req.horizon_days)
            if cached is not None and cached.input_signature == sig:
                if existing_job is not None:
                    existing_job.status = "completed"
                    existing_job.items_processed = cached.observation_count
                    existing_job.summary = {"cached": True, "forecast_id": str(cached.id)}
                    existing_job.completed_at = dt.datetime.now(dt.UTC)
                    db.add(existing_job)
                    db.commit()
                return self._serialize_overview(cached, is_stale=False)

        txs = self.repo.list_eligible_transactions(db, user_id, date_to=as_of_date)
        expenses = [t for t in txs if t.transaction_type == "expense"]
        incomes = [t for t in txs if t.transaction_type == "income"]
        accounts = self.repo.list_active_accounts(db, user_id)
        cat_map = self.repo.list_categorizations_map(db, user_id)
        anomalies = self.repo.list_recent_anomalies(db, user_id)

        commitments, _, _ = collect_upcoming_commitments(
            db,
            self.repo,
            user_id,
            as_of_date=as_of_date,
            horizon_days=req.horizon_days,
        )
        exp_fc, daily_disc_rate, dow_mult = forecast_expenses(
            expenses=expenses,
            commitments=commitments,
            as_of_date=as_of_date,
            horizon_days=req.horizon_days,
        )
        inc_fc, daily_inc_rate = forecast_income(
            incomes=incomes,
            horizon_days=req.horizon_days,
        )
        cat_forecasts = forecast_categories(
            expenses=expenses,
            cat_map=cat_map,
            horizon_days=req.horizon_days,
        )
        cashflow, balances = build_cashflow_and_balances(
            accounts=accounts,
            expenses=expenses,
            incomes=incomes,
            commitments=commitments,
            expense_fc=exp_fc,
            income_fc=inc_fc,
            daily_disc_expense_rate=daily_disc_rate,
            dow_multipliers=dow_mult,
            daily_income_rate=daily_inc_rate,
            as_of_date=as_of_date,
            horizon_days=req.horizon_days,
            timezone=tz,
        )
        risks = detect_financial_risks(
            cashflow=cashflow,
            income=inc_fc,
            expenses=exp_fc,
            categories=cat_forecasts,
            commitments=commitments,
            balances=balances,
            low_balance_threshold=req.low_balance_threshold,
        )
        savings = compute_savings_projection(
            income=inc_fc,
            expenses=exp_fc,
            cashflow=cashflow,
            horizon_days=req.horizon_days,
        )

        all_dates = [t.transaction_date for t in txs]
        cov_days = ((max(all_dates) - min(all_dates)).days + 1) if len(all_dates) >= 2 else len(all_dates)
        status_val = (
            "insufficient_data"
            if exp_fc.confidence_label == "insufficient_data"
            and inc_fc.confidence_label == "insufficient_data"
            else "completed"
        )

        summary_payload = {
            "cashflow": cashflow.model_dump(mode="json"),
            "expenses": exp_fc.model_dump(mode="json"),
            "income": inc_fc.model_dump(mode="json"),
            "categories": [c.model_dump(mode="json") for c in cat_forecasts],
            "commitments": [c.model_dump(mode="json") for c in commitments],
            "balances": [b.model_dump(mode="json") for b in balances],
            "risks": [r.model_dump(mode="json") for r in risks],
            "savings": savings.model_dump(mode="json"),
        }

        forecast = FinancialForecast(
            user_id=user_id,
            forecast_type="comprehensive",
            horizon_days=req.horizon_days,
            as_of_date=as_of_date,
            data_cutoff_date=cashflow.data_cutoff_date,
            timezone=tz,
            method=exp_fc.method,
            method_version="1.0",
            confidence_label=exp_fc.confidence_label,
            confidence_score=exp_fc.confidence_score,
            observation_count=len(txs),
            historical_days_covered=cov_days,
            status=status_val,
            assumptions=cashflow.assumptions,
            limitations=cashflow.limitations,
            summary_payload=summary_payload,
            input_signature=sig,
        )
        db.add(forecast)
        db.flush()

        # Store normalized ForecastValue rows for traceability
        for mp in cashflow.monthly_points:
            db.add(
                ForecastValue(
                    forecast_id=forecast.id,
                    user_id=user_id,
                    series_type="cashflow_monthly",
                    target_date=mp.target_date,
                    label=mp.label,
                    predicted_amount=mp.net_cashflow,
                    certainty_label=mp.source_kind,
                    is_prediction=mp.is_prediction,
                    meta={
                        "income": str(mp.income_amount),
                        "expense": str(mp.expense_amount),
                        "closing": str(mp.projected_closing_balance),
                    },
                )
            )
        for cf in cat_forecasts[:12]:
            db.add(
                ForecastValue(
                    forecast_id=forecast.id,
                    user_id=user_id,
                    series_type="category",
                    label=cf.category_name,
                    reference_id=cf.category_id,
                    reference_type="category",
                    baseline_amount=cf.historical_monthly_avg,
                    predicted_amount=cf.predicted_amount,
                    lower_bound=cf.lower_bound,
                    upper_bound=cf.upper_bound,
                    certainty_label=cf.confidence_label,
                    is_prediction=True,
                )
            )
        for comm in commitments[:25]:
            db.add(
                ForecastValue(
                    forecast_id=forecast.id,
                    user_id=user_id,
                    series_type="commitment",
                    target_date=comm.due_date,
                    label=comm.name,
                    reference_id=comm.source_id,
                    reference_type=comm.source_type,
                    predicted_amount=comm.expected_amount,
                    certainty_label=comm.amount_certainty,
                    is_prediction=True,
                )
            )

        explanations = build_forecast_explanations(
            forecast_id=forecast.id,
            user_id=user_id,
            expenses=expenses,
            incomes=incomes,
            expense_fc=exp_fc,
            income_fc=inc_fc,
            cashflow=cashflow,
            categories=cat_forecasts,
            commitments=commitments,
            risks=risks,
            recent_anomalies=anomalies,
        )
        for ex in explanations:
            db.add(ex)

        if existing_job is not None:
            existing_job.status = "completed"
            existing_job.items_processed = len(txs)
            existing_job.summary = {"cached": False, "forecast_id": str(forecast.id)}
            existing_job.completed_at = dt.datetime.now(dt.UTC)
            db.add(existing_job)

        db.commit()
        refreshed = self.repo.get_forecast_by_id(db, user_id, forecast.id) or forecast
        return self._serialize_overview(refreshed, is_stale=False)

    def get_overview(
        self,
        db: Session,
        user: User,
        *,
        horizon_days: int = 30,
        low_balance_threshold: Decimal = Decimal("5000.00"),
    ) -> ForecastingOverviewResponse:
        tz = self.repo.get_user_timezone(db, user.id)
        as_of_date = resolve_user_today(tz)
        sig = self._compute_input_signature(
            db,
            user.id,
            as_of_date=as_of_date,
            horizon_days=horizon_days,
            low_balance_threshold=low_balance_threshold,
        )
        latest = self.repo.get_latest_forecast(db, user.id, horizon_days=horizon_days)
        if latest is not None:
            return self._serialize_overview(latest, is_stale=(latest.input_signature != sig))
        return self.generate_forecast_for_user(
            db,
            user.id,
            GenerateForecastRequest(
                horizon_days=horizon_days,
                force_refresh=False,
                low_balance_threshold=low_balance_threshold,
            ),
        )

    def enqueue_forecast_job(self, db: Session, user: User) -> AiProcessingJob:
        existing = self.repo.get_active_forecast_job(db, user.id)
        if existing is not None:
            return existing
        job = AiProcessingJob(
            user_id=user.id,
            job_type="forecast_generation",
            status="queued",
            provider_name="local",
            model_name="deterministic_forecast_v1",
            prompt_version="phase9_v1",
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    def list_history(
        self, db: Session, user: User, *, horizon_days: int | None = None
    ) -> list[ForecastRecordResponse]:
        rows = self.repo.list_forecast_history(db, user.id, horizon_days=horizon_days)
        return [ForecastRecordResponse.model_validate(r) for r in rows]

    def get_forecast_detail(
        self, db: Session, user: User, forecast_id: uuid.UUID
    ) -> ForecastingOverviewResponse:
        rec = self.repo.get_forecast_by_id(db, user.id, forecast_id)
        if rec is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Forecast not found.")
        return self._serialize_overview(rec, is_stale=False)

    def get_forecast_explanations(
        self, db: Session, user: User, forecast_id: uuid.UUID
    ) -> list[ForecastExplanationItem]:
        rec = self.repo.get_forecast_by_id(db, user.id, forecast_id)
        if rec is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Forecast not found.")
        return [ForecastExplanationItem.model_validate(e) for e in rec.explanations]

    def run_scenario(
        self, db: Session, user: User, req: ForecastScenarioRequest
    ) -> ForecastScenarioResponse:
        overview = self.get_overview(db, user, horizon_days=req.horizon_days)
        cancelled_set = {str(sid) for sid in req.cancelled_subscription_ids}
        cancelled_savings = sum(
            (
                c.expected_amount
                for c in overview.commitments
                if c.source_type == "subscription"
                and c.source_id in cancelled_set
                and c.expected_amount is not None
            ),
            Decimal("0.00"),
        )
        baseline, scenario, delta = evaluate_what_if_scenario(
            req=req,
            baseline_cashflow=overview.cashflow,
            categories=overview.categories,
            cancelled_subscription_savings=cancelled_savings,
        )

        params = req.model_dump(mode="json")
        if not req.save_scenario:
            return ForecastScenarioResponse(
                name=req.name,
                horizon_days=req.horizon_days,
                parameters=params,
                baseline_summary=baseline,
                scenario_summary=scenario,
                delta_summary=delta,
            )

        rec = ForecastScenario(
            user_id=user.id,
            name=req.name,
            horizon_days=req.horizon_days,
            parameters=params,
            baseline_summary=baseline.model_dump(mode="json"),
            scenario_summary=scenario.model_dump(mode="json"),
            delta_summary={k: str(v) for k, v in delta.items()},
        )
        db.add(rec)
        db.commit()
        db.refresh(rec)
        return self._serialize_scenario(rec)

    @staticmethod
    def _serialize_scenario(rec: ForecastScenario) -> ForecastScenarioResponse:
        return ForecastScenarioResponse(
            id=rec.id,
            name=rec.name,
            horizon_days=rec.horizon_days,
            parameters=rec.parameters,
            baseline_summary=ForecastScenarioOutcome.model_validate(rec.baseline_summary),
            scenario_summary=ForecastScenarioOutcome.model_validate(rec.scenario_summary),
            delta_summary={k: Decimal(str(v)) for k, v in rec.delta_summary.items()},
            created_at=rec.created_at,
        )

    def list_scenarios(self, db: Session, user: User) -> list[ForecastScenarioResponse]:
        return [self._serialize_scenario(r) for r in self.repo.list_scenarios(db, user.id)]

    def get_scenario(
        self, db: Session, user: User, scenario_id: uuid.UUID
    ) -> ForecastScenarioResponse:
        rec = self.repo.get_scenario_by_id(db, user.id, scenario_id)
        if rec is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found.")
        return self._serialize_scenario(rec)

    def delete_scenario(self, db: Session, user: User, scenario_id: uuid.UUID) -> None:
        rec = self.repo.get_scenario_by_id(db, user.id, scenario_id)
        if rec is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found.")
        db.delete(rec)
        db.commit()

    def evaluate_accuracy(
        self, db: Session, user: User, *, horizon_days: int = 30
    ) -> ForecastEvaluationResponse:
        tz = self.repo.get_user_timezone(db, user.id)
        as_of_date = resolve_user_today(tz)
        ev = run_time_aware_backtest(
            db, self.repo, user.id, as_of_date=as_of_date, horizon_days=horizon_days
        )
        db.commit()
        db.refresh(ev)
        return ForecastEvaluationResponse.model_validate(ev)

    def list_evaluations(self, db: Session, user: User) -> list[ForecastEvaluationResponse]:
        rows = self.repo.list_evaluations(db, user.id)
        return [ForecastEvaluationResponse.model_validate(r) for r in rows]
