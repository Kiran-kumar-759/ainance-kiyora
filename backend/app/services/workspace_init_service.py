from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.bills import Bill
from app.models.documents import FinancialDocument
from app.models.finance import BankingConnection, FinancialTransaction
from app.models.loans import Loan
from app.models.onboarding import UserOnboardingState
from app.models.subscriptions import Subscription
from app.models.user import User
from app.repositories.finance.account_repository import AccountRepository
from app.repositories.intelligence.intelligence_repository import IntelligenceRepository
from app.repositories.onboarding_repository import OnboardingRepository
from app.repositories.user_repository import UserRepository
from app.schemas.forecasting import GenerateForecastRequest
from app.schemas.onboarding import InitializationStatusResponse, InitializationStepStatus
from app.services.ai.categorization_service import run_categorization_for_user
from app.services.assistant.rag_service import reindex_user_documents
from app.services.finance.category_service import CategoryService
from app.services.finance.ledger_service import LedgerService
from app.services.forecasting.forecast_service import ForecastService

STEP_DEFINITIONS: tuple[tuple[str, str], ...] = (
    ("preparing_workspace", "Preparing your financial workspace"),
    ("verifying_accounts", "Verifying your accounts"),
    ("organizing_transactions", "Organizing available transactions"),
    ("preparing_insights", "Preparing your financial insights"),
    ("initializing_dashboard", "Initializing your dashboard"),
    ("workspace_ready", "Your financial workspace is ready"),
)


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()


def _initial_steps() -> list[dict[str, Any]]:
    return [
        {
            "key": key,
            "label": label,
            "status": "pending",
            "detail": None,
            "started_at": None,
            "completed_at": None,
        }
        for key, label in STEP_DEFINITIONS
    ]


class WorkspaceInitializationService:
    """
    Runs deterministic, idempotent workspace initialization on real user-owned records
    stored in PostgreSQL. Handles empty or skipped setups honestly without creating dummy data.
    """

    def __init__(self):
        self.onboarding_repo = OnboardingRepository()
        self.user_repo = UserRepository()
        self.account_repo = AccountRepository()
        self.category_service = CategoryService()
        self.ledger_service = LedgerService()
        self.intel_repo = IntelligenceRepository()
        self.forecast_service = ForecastService()

    def _serialize_steps(self, raw_steps: list[dict[str, Any]]) -> list[InitializationStepStatus]:
        return [InitializationStepStatus.model_validate(s) for s in (raw_steps or [])]

    def _step_preparing_workspace(self, db: Session, user: User) -> str:
        self.category_service.seed_default_categories(db, commit=False)
        return "System categories and Indian workspace defaults verified."

    def _step_verifying_accounts(self, db: Session, user: User) -> tuple[str, dict[str, int]]:
        accounts = self.account_repo.list_by_user(db, user.id, include_archived=False)
        for acc in accounts:
            self.ledger_service.recalculate_and_sync_account_balance(
                db, acc.id, acc.account_type
            )
        active_conns = int(
            db.execute(
                select(func.count(BankingConnection.id)).where(
                    BankingConnection.user_id == user.id,
                    BankingConnection.status == "connected",
                )
            ).scalar_one()
            or 0
        )
        detail = (
            f"Verified {len(accounts)} active account(s) across {active_conns} banking connection(s)."
            if accounts
            else "No accounts added yet; empty workspace verified cleanly."
        )
        return detail, {"accounts_verified": len(accounts), "active_connections": active_conns}

    def _step_organizing_transactions(self, db: Session, user: User) -> tuple[str, dict[str, int]]:
        tx_count = int(
            db.execute(
                select(func.count(FinancialTransaction.id)).where(
                    FinancialTransaction.user_id == user.id
                )
            ).scalar_one()
            or 0
        )
        if tx_count == 0:
            return (
                "No transactions available yet; add or import transactions anytime to run categorization.",
                {"transactions_count": 0, "categorized_count": 0},
            )
        outcome = run_categorization_for_user(
            db=db,
            repo=self.intel_repo,
            user_id=user.id,
            reanalyze_all=False,
            use_ai_fallback=False,
        )
        return (
            f"Organized {tx_count} transaction(s) ({outcome.processed} newly analyzed via deterministic rules).",
            {"transactions_count": tx_count, "categorized_count": outcome.processed},
        )

    def _step_preparing_insights(self, db: Session, user: User) -> tuple[str, dict[str, Any]]:
        bills_count = int(
            db.execute(select(func.count(Bill.id)).where(Bill.user_id == user.id)).scalar_one()
            or 0
        )
        subs_count = int(
            db.execute(
                select(func.count(Subscription.id)).where(Subscription.user_id == user.id)
            ).scalar_one()
            or 0
        )
        loans_count = int(
            db.execute(select(func.count(Loan.id)).where(Loan.user_id == user.id)).scalar_one()
            or 0
        )
        tx_count = int(
            db.execute(
                select(func.count(FinancialTransaction.id)).where(
                    FinancialTransaction.user_id == user.id
                )
            ).scalar_one()
            or 0
        )
        forecast_status = "insufficient_data"
        if tx_count >= 3 or (bills_count + subs_count + loans_count) > 0:
            overview = self.forecast_service.generate_forecast_for_user(
                db,
                user.id,
                GenerateForecastRequest(horizon_days=30, force_refresh=False),
            )
            forecast_status = overview.forecast.status
            detail = (
                f"Prepared summaries ({bills_count} bills, {subs_count} subscriptions, "
                f"{loans_count} loans) and initialized forecast (status: {forecast_status})."
            )
        else:
            detail = (
                "Insights and forecasting ready to populate once real transactions or commitments are added."
            )
        return detail, {
            "bills_count": bills_count,
            "subscriptions_count": subs_count,
            "loans_count": loans_count,
            "forecast_status": forecast_status,
        }

    def _step_initializing_dashboard(self, db: Session, user: User) -> tuple[str, dict[str, int]]:
        doc_count = int(
            db.execute(
                select(func.count(FinancialDocument.id)).where(
                    FinancialDocument.user_id == user.id
                )
            ).scalar_one()
            or 0
        )
        chunks_indexed = 0
        if doc_count > 0:
            _, chunks_indexed, _ = reindex_user_documents(db, user.id)
        detail = (
            f"Dashboard initialized with {doc_count} document(s) ({chunks_indexed} RAG chunks indexed)."
            if doc_count > 0
            else "Dashboard initialized with zero-data empty state ready."
        )
        return detail, {"documents_count": doc_count, "rag_chunks_indexed": chunks_indexed}

    def get_initialization_status(
        self, db: Session, user: User, state: UserOnboardingState
    ) -> InitializationStatusResponse:
        return InitializationStatusResponse(
            initialization_status=state.initialization_status,  # type: ignore[arg-type]
            initialization_error=state.initialization_error,
            initialization_started_at=state.initialization_started_at,
            initialization_completed_at=state.initialization_completed_at,
            steps=self._serialize_steps(state.initialization_steps),
            dashboard_access_allowed=bool(user.onboarding_completed),
            onboarding_completed=bool(user.onboarding_completed),
            current_stage=state.current_stage,
            summary=(state.financial_profile or {}).get("last_initialization_summary", {}),
        )

    def run_initialization(
        self,
        db: Session,
        user: User,
        state: UserOnboardingState,
        *,
        force: bool = False,
    ) -> InitializationStatusResponse:
        """
        Executes onboarding workspace initialization atomically across real data.
        Prevents concurrent duplicate execution and persists step-level failure for retry.
        """
        if state.initialization_status == "in_progress":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Workspace initialization is already in progress.",
            )

        if state.initialization_status == "completed" and user.onboarding_completed and not force:
            return self.get_initialization_status(db, user, state)

        steps = _initial_steps()
        state.initialization_status = "in_progress"
        state.initialization_error = None
        state.initialization_started_at = datetime.now(UTC)
        state.initialization_completed_at = None
        state.current_stage = "data_processing"
        state.initialization_steps = steps
        self.onboarding_repo.save(db, state, commit=True)

        summary: dict[str, Any] = {}
        active_index = 0

        try:
            # Step 1
            active_index = 0
            steps[0]["status"] = "in_progress"
            steps[0]["started_at"] = _iso_now()
            steps[0]["detail"] = self._step_preparing_workspace(db, user)
            steps[0]["status"] = "completed"
            steps[0]["completed_at"] = _iso_now()

            # Step 2
            active_index = 1
            steps[1]["status"] = "in_progress"
            steps[1]["started_at"] = _iso_now()
            detail_2, sum_2 = self._step_verifying_accounts(db, user)
            summary.update(sum_2)
            steps[1]["detail"] = detail_2
            steps[1]["status"] = "completed"
            steps[1]["completed_at"] = _iso_now()

            # Step 3
            active_index = 2
            steps[2]["status"] = "in_progress"
            steps[2]["started_at"] = _iso_now()
            detail_3, sum_3 = self._step_organizing_transactions(db, user)
            summary.update(sum_3)
            steps[2]["detail"] = detail_3
            steps[2]["status"] = "completed"
            steps[2]["completed_at"] = _iso_now()

            # Step 4
            active_index = 3
            steps[3]["status"] = "in_progress"
            steps[3]["started_at"] = _iso_now()
            detail_4, sum_4 = self._step_preparing_insights(db, user)
            summary.update(sum_4)
            steps[3]["detail"] = detail_4
            steps[3]["status"] = "completed"
            steps[3]["completed_at"] = _iso_now()

            # Step 5
            active_index = 4
            steps[4]["status"] = "in_progress"
            steps[4]["started_at"] = _iso_now()
            detail_5, sum_5 = self._step_initializing_dashboard(db, user)
            summary.update(sum_5)
            steps[4]["detail"] = detail_5
            steps[4]["status"] = "completed"
            steps[4]["completed_at"] = _iso_now()

            # Step 6
            active_index = 5
            steps[5]["status"] = "completed"
            steps[5]["started_at"] = _iso_now()
            steps[5]["completed_at"] = _iso_now()
            steps[5]["detail"] = "Financial workspace initialized and ready for dashboard access."

            completed_stages = list(state.completed_stages or [])
            for stg in ("financial_data_setup", "data_processing", "completed"):
                if stg not in completed_stages:
                    completed_stages.append(stg)

            if state.financial_setup_skipped:
                state.financial_setup_status = "skipped"
            elif summary.get("active_connections", 0) > 0 and summary.get("accounts_verified", 0) > 0:
                state.financial_setup_status = "connected"
            elif summary.get("accounts_verified", 0) > 0:
                state.financial_setup_status = "completed"

            profile_meta = dict(state.financial_profile or {})
            profile_meta["last_initialization_summary"] = summary
            state.financial_profile = profile_meta
            state.completed_stages = completed_stages
            state.current_stage = "completed"
            state.current_step = 5
            state.initialization_status = "completed"
            state.initialization_error = None
            state.initialization_completed_at = datetime.now(UTC)
            state.initialization_steps = steps

            self.onboarding_repo.save(db, state, commit=False)
            self.user_repo.update(db, user, onboarding_completed=True)
            db.refresh(state)
            return self.get_initialization_status(db, user, state)
        except Exception as exc:
            db.rollback()
            fresh_state = self.onboarding_repo.get_or_create(
                db, user.id, already_completed=user.onboarding_completed
            )
            steps[active_index]["status"] = "failed"
            steps[active_index]["detail"] = str(exc)[:300]
            steps[active_index]["completed_at"] = _iso_now()
            fresh_state.initialization_status = "failed"
            fresh_state.initialization_error = str(exc)[:500]
            fresh_state.initialization_steps = steps
            fresh_state.current_stage = "data_processing"
            self.onboarding_repo.save(db, fresh_state, commit=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Workspace initialization failed during '{steps[active_index]['key']}'. Retry is available.",
            ) from exc
