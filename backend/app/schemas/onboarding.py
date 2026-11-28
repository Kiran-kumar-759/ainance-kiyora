import datetime as dt
import uuid
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.user import UserPreferenceResponse

OnboardingStage = Literal[
    "registered",
    "profile_setup",
    "financial_data_setup",
    "data_processing",
    "skipped",
    "completed",
]

FinancialSetupMethod = Literal[
    "bank_connect",
    "manual_account",
    "statement_import",
    "document_upload",
    "skip",
]


class OnboardingStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    onboarding_completed: bool
    is_email_verified: bool
    full_name: str
    current_step: int = 1
    current_stage: str = "registered"
    dashboard_access_allowed: bool = False
    preferences: UserPreferenceResponse


class OnboardingUpdateRequest(BaseModel):
    full_name: str | None = Field(None, min_length=2, max_length=100)
    first_name: str | None = Field(None, min_length=1, max_length=60)
    last_name: str | None = Field(None, min_length=1, max_length=60)
    current_step: int | None = Field(None, ge=1, le=5)
    preferred_currency: str | None = Field(None, max_length=10)
    locale: str | None = Field(None, max_length=20)
    timezone: str | None = Field(None, max_length=50)
    date_format: str | None = Field(None, max_length=20)
    notification_preferences: dict[str, Any] | None = None
    phone_number: str | None = Field(None, max_length=20)
    monthly_budget: Decimal | None = Field(None, ge=0)
    monthly_income_range: str | None = Field(None, max_length=60)
    financial_goals: list[str] | None = None


class OnboardingProfileRequest(BaseModel):
    first_name: str | None = Field(None, min_length=1, max_length=60)
    last_name: str | None = Field(None, max_length=60)
    full_name: str | None = Field(None, min_length=2, max_length=100)
    phone_number: str | None = Field(None, max_length=20)
    preferred_currency: str = Field(default="INR", max_length=10)
    locale: str = Field(default="en-IN", max_length=20)
    timezone: str = Field(default="Asia/Kolkata", max_length=50)
    date_format: str = Field(default="DD/MM/YYYY", max_length=20)
    monthly_budget: Decimal | None = Field(None, ge=0)
    monthly_income_range: str | None = Field(None, max_length=60)
    financial_goals: list[str] = Field(default_factory=list, max_length=10)
    notification_preferences: dict[str, Any] | None = None


class OnboardingFinancialSetupSelectRequest(BaseModel):
    setup_method: FinancialSetupMethod
    bank_id: str | None = Field(None, max_length=60)


class OnboardingSkipFinancialSetupRequest(BaseModel):
    complete_onboarding: bool = Field(
        default=False,
        description="When true, skips financial setup and completes onboarding immediately",
    )
    reason: str | None = Field(None, max_length=200)


class OnboardingInitializeRequest(BaseModel):
    force: bool = Field(
        default=False,
        description="Re-run initialization even if previously completed",
    )


class InitializationStepStatus(BaseModel):
    key: str
    label: str
    status: Literal["pending", "in_progress", "completed", "skipped", "failed"]
    detail: str | None = None
    started_at: dt.datetime | None = None
    completed_at: dt.datetime | None = None


class InitializationStatusResponse(BaseModel):
    initialization_status: Literal["not_started", "in_progress", "completed", "failed"]
    initialization_error: str | None = None
    initialization_started_at: dt.datetime | None = None
    initialization_completed_at: dt.datetime | None = None
    steps: list[InitializationStepStatus] = Field(default_factory=list)
    dashboard_access_allowed: bool
    onboarding_completed: bool
    current_stage: str
    summary: dict[str, Any] = Field(default_factory=dict)


class OnboardingProfileSummary(BaseModel):
    first_name: str
    last_name: str
    full_name: str
    email: str
    phone_number: str | None = None
    country: str = "India"
    financial_year: str = "April-March"
    monthly_budget: Decimal | None = None
    monthly_income_range: str | None = None
    financial_goals: list[str] = Field(default_factory=list)


class OnboardingComprehensiveStatusResponse(BaseModel):
    user_id: uuid.UUID
    onboarding_completed: bool
    dashboard_access_allowed: bool
    required_gate_view: Literal["onboarding", "dashboard"]
    is_email_verified: bool
    current_stage: str
    completed_stages: list[str]
    current_step: int
    profile_completed: bool
    profile: OnboardingProfileSummary
    financial_setup_status: str
    selected_setup_method: str | None = None
    financial_setup_skipped: bool
    has_active_banking_connection: bool
    accounts_count: int
    transactions_count: int
    pending_import_batches_count: int
    pending_documents_count: int
    initialization_status: str
    initialization_steps: list[InitializationStepStatus] = Field(default_factory=list)
    initialization_error: str | None = None
    next_action: str
    guidance_message: str
    preferences: UserPreferenceResponse


class DashboardAccessResponse(BaseModel):
    allowed: bool
    onboarding_completed: bool
    current_stage: str
    required_gate_view: Literal["onboarding", "dashboard"]
    next_action: str
    message: str
