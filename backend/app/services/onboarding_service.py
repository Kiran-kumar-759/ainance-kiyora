from __future__ import annotations

import re
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.documents import FinancialDocument
from app.models.finance import BankingConnection, FinancialAccount, FinancialTransaction
from app.models.imports import ImportBatch
from app.models.onboarding import UserOnboardingState
from app.models.user import User
from app.repositories.onboarding_repository import OnboardingRepository
from app.repositories.preference_repository import PreferenceRepository
from app.repositories.user_repository import UserRepository
from app.schemas.onboarding import (
    DashboardAccessResponse,
    InitializationStatusResponse,
    InitializationStepStatus,
    OnboardingComprehensiveStatusResponse,
    OnboardingFinancialSetupSelectRequest,
    OnboardingProfileRequest,
    OnboardingProfileSummary,
    OnboardingSkipFinancialSetupRequest,
    OnboardingStatusResponse,
    OnboardingUpdateRequest,
)
from app.schemas.user import UserPreferenceResponse
from app.services.workspace_init_service import WorkspaceInitializationService

_PHONE_RE = re.compile(r"^\+?[0-9\-\s]{7,18}$")

_VALID_STAGE_TRANSITIONS: dict[str, set[str]] = {
    "registered": {"registered", "profile_setup", "financial_data_setup", "data_processing", "skipped", "completed"},
    "profile_setup": {"profile_setup", "financial_data_setup", "data_processing", "skipped", "completed"},
    "financial_data_setup": {"financial_data_setup", "data_processing", "skipped", "completed", "profile_setup"},
    "data_processing": {"data_processing", "completed", "financial_data_setup", "skipped"},
    "skipped": {"skipped", "financial_data_setup", "data_processing", "completed", "profile_setup"},
    "completed": {"completed"},
}


def _split_name(full_name: str) -> tuple[str, str]:
    parts = (full_name or "").strip().split(None, 1)
    if not parts:
        return "", ""
    return parts[0], parts[1] if len(parts) > 1 else ""


def _resolve_names(
    *,
    current_full_name: str,
    full_name: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
) -> tuple[str, str, str]:
    if first_name is not None or last_name is not None:
        cur_first, cur_last = _split_name(current_full_name)
        first_val = first_name.strip() if first_name is not None else cur_first
        last_val = last_name.strip() if last_name is not None else cur_last
        combined = f"{first_val} {last_val}".strip() or current_full_name
        return combined, first_val, last_val
    if full_name is not None and full_name.strip():
        cleaned = full_name.strip()
        first_val, last_val = _split_name(cleaned)
        return cleaned, first_val, last_val
    first_val, last_val = _split_name(current_full_name)
    return current_full_name, first_val, last_val


def _append_stage(stages: list[str] | None, stage: str) -> list[str]:
    result = list(stages or [])
    if stage not in result:
        result.append(stage)
    return result


class OnboardingService:
    """Service orchestrating multi-step user onboarding, state machine transitions, and workspace setup."""

    def __init__(
        self,
        user_repo: UserRepository | None = None,
        pref_repo: PreferenceRepository | None = None,
        onboarding_repo: OnboardingRepository | None = None,
        init_service: WorkspaceInitializationService | None = None,
    ):
        self.user_repo = user_repo or UserRepository()
        self.pref_repo = pref_repo or PreferenceRepository()
        self.onboarding_repo = onboarding_repo or OnboardingRepository()
        self.init_service = init_service or WorkspaceInitializationService()

    def _ensure_state_and_pref(self, db: Session, user: User) -> tuple[UserOnboardingState, Any]:
        pref = self.pref_repo.get_by_user_id(db, user.id)
        if not pref:
            pref = self.pref_repo.create_defaults(db, user.id)
        state = self.onboarding_repo.get_or_create(
            db, user.id, already_completed=bool(user.onboarding_completed)
        )
        # Keep stage aligned if legacy onboarding_completed=True user existed before state table
        if user.onboarding_completed and state.current_stage != "completed":
            state.current_stage = "completed"
            state.completed_stages = _append_stage(state.completed_stages, "completed")
            state.current_step = 5
            if state.initialization_status == "not_started":
                state.initialization_status = "completed"
            self.onboarding_repo.save(db, state, commit=True)
        return state, pref

    def _validate_transition(self, current_stage: str, target_stage: str) -> None:
        allowed = _VALID_STAGE_TRANSITIONS.get(current_stage, set())
        if target_stage not in allowed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Invalid onboarding transition from '{current_stage}' to '{target_stage}'.",
            )

    def _collect_live_setup_signals(self, db: Session, user_id) -> dict[str, int | bool]:
        active_conns = int(
            db.execute(
                select(func.count(BankingConnection.id)).where(
                    BankingConnection.user_id == user_id,
                    BankingConnection.status == "connected",
                )
            ).scalar_one()
            or 0
        )
        accounts_count = int(
            db.execute(
                select(func.count(FinancialAccount.id)).where(
                    FinancialAccount.user_id == user_id,
                    FinancialAccount.status == "active",
                )
            ).scalar_one()
            or 0
        )
        tx_count = int(
            db.execute(
                select(func.count(FinancialTransaction.id)).where(
                    FinancialTransaction.user_id == user_id
                )
            ).scalar_one()
            or 0
        )
        pending_imports = int(
            db.execute(
                select(func.count(ImportBatch.id)).where(
                    ImportBatch.user_id == user_id,
                    ImportBatch.status.in_(["uploaded", "mapping_required", "ready_for_review"]),
                )
            ).scalar_one()
            or 0
        )
        pending_docs = int(
            db.execute(
                select(func.count(FinancialDocument.id)).where(
                    FinancialDocument.user_id == user_id,
                    FinancialDocument.processing_status.in_(["queued", "processing", "needs_review"]),
                )
            ).scalar_one()
            or 0
        )
        docs_total = int(
            db.execute(
                select(func.count(FinancialDocument.id)).where(
                    FinancialDocument.user_id == user_id,
                    FinancialDocument.processing_status != "rejected",
                )
            ).scalar_one()
            or 0
        )
        return {
            "has_active_banking_connection": active_conns > 0,
            "accounts_count": accounts_count,
            "transactions_count": tx_count,
            "pending_import_batches_count": pending_imports,
            "pending_documents_count": pending_docs,
            "docs_total": docs_total,
        }

    def get_status(self, db: Session, user: User) -> OnboardingStatusResponse:
        state, pref = self._ensure_state_and_pref(db, user)
        return OnboardingStatusResponse(
            onboarding_completed=bool(user.onboarding_completed),
            is_email_verified=bool(user.is_email_verified),
            full_name=user.full_name,
            current_step=state.current_step,
            current_stage=state.current_stage,
            dashboard_access_allowed=bool(user.onboarding_completed),
            preferences=UserPreferenceResponse.model_validate(pref),
        )

    def get_comprehensive_status(
        self, db: Session, user: User
    ) -> OnboardingComprehensiveStatusResponse:
        state, pref = self._ensure_state_and_pref(db, user)
        signals = self._collect_live_setup_signals(db, user.id)

        # Derive dynamic financial_setup_status accurately from real persisted DB state
        derived_setup_status = state.financial_setup_status
        if signals["has_active_banking_connection"] and signals["accounts_count"] > 0:
            derived_setup_status = "connected"
        elif signals["accounts_count"] > 0 and derived_setup_status in {"not_started", "selected", "skipped"}:
            derived_setup_status = "manual_added" if state.selected_setup_method == "manual_account" else "completed"
        elif signals["docs_total"] > 0 and derived_setup_status == "not_started":
            derived_setup_status = "documents_uploaded"

        # Derive honest next_action & guidance_message
        if user.onboarding_completed:
            next_action = "go_to_dashboard"
            if signals["accounts_count"] == 0 and signals["transactions_count"] == 0:
                guidance_message = (
                    "Onboarding is complete. Analytics, cash-flow forecasting, and personalized AI "
                    "insights will populate once you connect a bank account, add an account, or import statements."
                )
            else:
                guidance_message = "Onboarding completed. Your personalized dashboard and financial insights are active."
        elif not state.profile_completed and state.current_stage in {"registered", "profile_setup"}:
            next_action = "complete_profile"
            guidance_message = "Complete your profile and Indian regional preferences (INR, Asia/Kolkata) to continue."
        elif signals["pending_import_batches_count"] > 0:
            next_action = "finish_pending_import"
            guidance_message = "Finish mapping and confirming your uploaded bank statement batch."
        elif signals["pending_documents_count"] > 0:
            next_action = "review_uploaded_documents"
            guidance_message = "Review extracted OCR fields on your uploaded bill or receipt."
        elif state.initialization_status == "failed":
            next_action = "retry_initialization"
            guidance_message = "Workspace initialization encountered an issue. Retry initialization to activate your dashboard."
        elif (
            state.financial_setup_skipped
            or derived_setup_status in {"connected", "manual_added", "imported", "documents_uploaded", "completed", "skipped"}
            or signals["accounts_count"] > 0
        ):
            next_action = "initialize_workspace"
            guidance_message = (
                "Financial data setup recorded. Initialize your workspace to activate your dashboard."
                if not state.financial_setup_skipped
                else "Financial setup skipped cleanly. Initialize your workspace to enter the dashboard."
            )
        else:
            next_action = "choose_financial_setup"
            guidance_message = (
                "Choose how to set up your financial data: connect a bank, add an account manually, "
                "import a CSV/XLSX statement, upload a receipt, or skip for now."
            )

        meta = dict(state.financial_profile or {})
        fallback_first, fallback_last = _split_name(user.full_name)
        profile = OnboardingProfileSummary(
            first_name=meta.get("first_name") or fallback_first,
            last_name=meta.get("last_name") if meta.get("last_name") is not None else fallback_last,
            full_name=user.full_name,
            email=user.email,
            phone_number=meta.get("phone_number") or (pref.notification_preferences or {}).get("phone_number"),
            country=meta.get("country", "India"),
            financial_year=meta.get("financial_year", "April-March"),
            monthly_budget=meta.get("monthly_budget"),
            monthly_income_range=meta.get("monthly_income_range"),
            financial_goals=meta.get("financial_goals") or [],
        )

        steps = [InitializationStepStatus.model_validate(s) for s in (state.initialization_steps or [])]
        return OnboardingComprehensiveStatusResponse(
            user_id=user.id,
            onboarding_completed=bool(user.onboarding_completed),
            dashboard_access_allowed=bool(user.onboarding_completed),
            required_gate_view="dashboard" if user.onboarding_completed else "onboarding",
            is_email_verified=bool(user.is_email_verified),
            current_stage=state.current_stage,
            completed_stages=list(state.completed_stages or ["registered"]),
            current_step=state.current_step,
            profile_completed=bool(state.profile_completed),
            profile=profile,
            financial_setup_status=derived_setup_status,
            selected_setup_method=state.selected_setup_method,
            financial_setup_skipped=bool(state.financial_setup_skipped),
            has_active_banking_connection=bool(signals["has_active_banking_connection"]),
            accounts_count=int(signals["accounts_count"]),
            transactions_count=int(signals["transactions_count"]),
            pending_import_batches_count=int(signals["pending_import_batches_count"]),
            pending_documents_count=int(signals["pending_documents_count"]),
            initialization_status=state.initialization_status,
            initialization_steps=steps,
            initialization_error=state.initialization_error,
            next_action=next_action,
            guidance_message=guidance_message,
            preferences=UserPreferenceResponse.model_validate(pref),
        )

    def update_step(
        self,
        db: Session,
        user: User,
        req: OnboardingUpdateRequest,
    ) -> OnboardingStatusResponse:
        """Updates optional profile and regional preferences during onboarding cleanly."""
        state, pref = self._ensure_state_and_pref(db, user)

        combined_name, first_n, last_n = _resolve_names(
            current_full_name=user.full_name,
            full_name=req.full_name,
            first_name=req.first_name,
            last_name=req.last_name,
        )
        if combined_name != user.full_name:
            self.user_repo.update(db, user, full_name=combined_name)

        pref_updates: dict[str, Any] = {}
        if req.preferred_currency is not None:
            pref_updates["preferred_currency"] = req.preferred_currency
        if req.locale is not None:
            pref_updates["locale"] = req.locale
        if req.timezone is not None:
            pref_updates["timezone"] = req.timezone
        if req.date_format is not None:
            pref_updates["date_format"] = req.date_format

        current_notifs = (
            dict(pref.notification_preferences)
            if isinstance(pref.notification_preferences, dict)
            else {}
        )
        if req.current_step is not None:
            current_notifs["current_step"] = req.current_step
            state.current_step = req.current_step
        if req.notification_preferences is not None:
            current_notifs.update(req.notification_preferences)
        if req.phone_number is not None:
            if req.phone_number and not _PHONE_RE.match(req.phone_number.strip()):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Enter a valid phone number.",
                )
            current_notifs["phone_number"] = req.phone_number.strip() or None
        pref_updates["notification_preferences"] = current_notifs
        self.pref_repo.update(db, pref, **pref_updates)

        meta = dict(state.financial_profile or {})
        meta.setdefault("country", "India")
        meta.setdefault("financial_year", "April-March")
        meta["first_name"] = first_n
        meta["last_name"] = last_n
        if req.phone_number is not None:
            meta["phone_number"] = req.phone_number.strip() or None
        if req.monthly_budget is not None:
            meta["monthly_budget"] = str(req.monthly_budget)
        if req.monthly_income_range is not None:
            meta["monthly_income_range"] = req.monthly_income_range
        if req.financial_goals is not None:
            meta["financial_goals"] = req.financial_goals
        state.financial_profile = meta

        if not user.onboarding_completed and state.current_stage == "registered":
            state.current_stage = "profile_setup"
            state.completed_stages = _append_stage(state.completed_stages, "profile_setup")
        self.onboarding_repo.save(db, state, commit=True)

        return self.get_status(db, user)

    def save_profile_and_preferences(
        self,
        db: Session,
        user: User,
        req: OnboardingProfileRequest,
    ) -> OnboardingComprehensiveStatusResponse:
        """Persists Step 3 profile and Indian financial preferences and advances to financial setup."""
        state, _ = self._ensure_state_and_pref(db, user)
        patch = OnboardingUpdateRequest(
            full_name=req.full_name,
            first_name=req.first_name,
            last_name=req.last_name,
            phone_number=req.phone_number,
            preferred_currency=req.preferred_currency,
            locale=req.locale,
            timezone=req.timezone,
            date_format=req.date_format,
            notification_preferences=req.notification_preferences,
            monthly_budget=req.monthly_budget,
            monthly_income_range=req.monthly_income_range,
            financial_goals=req.financial_goals,
            current_step=4 if not user.onboarding_completed else state.current_step,
        )
        self.update_step(db, user, patch)
        state = self.onboarding_repo.get_or_create(
            db, user.id, already_completed=bool(user.onboarding_completed)
        )
        state.profile_completed = True
        state.completed_stages = _append_stage(state.completed_stages, "profile_setup")
        if not user.onboarding_completed:
            self._validate_transition(state.current_stage, "financial_data_setup")
            state.current_stage = "financial_data_setup"
            state.current_step = 4
        self.onboarding_repo.save(db, state, commit=True)
        return self.get_comprehensive_status(db, user)

    def select_financial_setup_method(
        self,
        db: Session,
        user: User,
        req: OnboardingFinancialSetupSelectRequest,
    ) -> OnboardingComprehensiveStatusResponse:
        state, _ = self._ensure_state_and_pref(db, user)
        if req.setup_method == "skip":
            return self.skip_financial_setup(
                db, user, OnboardingSkipFinancialSetupRequest(complete_onboarding=False)
            )

        if not user.onboarding_completed:
            self._validate_transition(state.current_stage, "financial_data_setup")
            state.current_stage = "financial_data_setup"
            state.current_step = 4

        state.selected_setup_method = req.setup_method
        state.financial_setup_skipped = False
        state.financial_setup_status = "selected"
        if req.bank_id:
            meta = dict(state.financial_profile or {})
            meta["selected_bank_id"] = req.bank_id
            state.financial_profile = meta
        self.onboarding_repo.save(db, state, commit=True)
        return self.get_comprehensive_status(db, user)

    def skip_financial_setup(
        self,
        db: Session,
        user: User,
        req: OnboardingSkipFinancialSetupRequest,
    ) -> OnboardingComprehensiveStatusResponse:
        """
        Records explicit decision to skip financial-data setup without fabricating accounts,
        transactions, balances, or marking a bank connected.
        """
        state, _ = self._ensure_state_and_pref(db, user)
        state.selected_setup_method = "skip"
        state.financial_setup_skipped = True
        state.financial_setup_status = "skipped"
        state.completed_stages = _append_stage(state.completed_stages, "skipped")
        if not user.onboarding_completed:
            self._validate_transition(state.current_stage, "skipped")
            state.current_stage = "skipped"
        if req.reason:
            meta = dict(state.financial_profile or {})
            meta["skip_reason"] = req.reason.strip()
            state.financial_profile = meta
        self.onboarding_repo.save(db, state, commit=True)

        if req.complete_onboarding:
            self.complete_onboarding(db, user)
        return self.get_comprehensive_status(db, user)

    def initialize_workspace(
        self, db: Session, user: User, *, force: bool = False
    ) -> InitializationStatusResponse:
        state, _ = self._ensure_state_and_pref(db, user)
        return self.init_service.run_initialization(db, user, state, force=force)

    def get_initialization_status(self, db: Session, user: User) -> InitializationStatusResponse:
        state, _ = self._ensure_state_and_pref(db, user)
        return self.init_service.get_initialization_status(db, user, state)

    def check_dashboard_access(self, db: Session, user: User) -> DashboardAccessResponse:
        state, _ = self._ensure_state_and_pref(db, user)
        if not user.onboarding_completed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Onboarding must be completed before accessing the dashboard.",
            )
        return DashboardAccessResponse(
            allowed=True,
            onboarding_completed=True,
            current_stage=state.current_stage,
            required_gate_view="dashboard",
            next_action="go_to_dashboard",
            message="Dashboard access granted.",
        )

    def complete_onboarding(self, db: Session, user: User) -> OnboardingStatusResponse:
        """Finalizes onboarding and persists completion status in PostgreSQL."""
        state, _ = self._ensure_state_and_pref(db, user)
        state.current_stage = "completed"
        state.completed_stages = _append_stage(state.completed_stages, "completed")
        state.current_step = 5
        if state.financial_setup_skipped:
            state.financial_setup_status = "skipped"
        self.onboarding_repo.save(db, state, commit=False)
        self.user_repo.update(db, user, onboarding_completed=True)
        return self.get_status(db, user)

    def skip_onboarding(self, db: Session, user: User) -> OnboardingStatusResponse:
        """Allows user to skip all optional onboarding setup steps without fake financial data."""
        state, _ = self._ensure_state_and_pref(db, user)
        state.selected_setup_method = state.selected_setup_method or "skip"
        state.financial_setup_skipped = True
        state.financial_setup_status = "skipped"
        state.completed_stages = _append_stage(state.completed_stages, "skipped")
        state.completed_stages = _append_stage(state.completed_stages, "completed")
        state.current_stage = "completed"
        state.current_step = 5
        self.onboarding_repo.save(db, state, commit=False)
        self.user_repo.update(db, user, onboarding_completed=True)
        return self.get_status(db, user)
