import datetime as dt
import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.bills import (
    BillReminderResponse,
    NotificationChannelsConfig,
)

LoanTypeLiteral = Literal[
    "personal",
    "education",
    "home",
    "vehicle",
    "gold",
    "business",
    "consumer_durable",
    "other",
]

LoanStatusLiteral = Literal["active", "closed", "overdue", "paused", "archived"]
InterestRateTypeLiteral = Literal["fixed", "floating"]
CalculationMethodLiteral = Literal["reducing_balance", "flat_rate", "zero_interest"]
EmiFrequencyLiteral = Literal["monthly", "quarterly", "weekly"]


class EmiCalculatorRequest(BaseModel):
    principal: Decimal = Field(..., gt=Decimal("0.00"), decimal_places=2)
    annual_interest_rate: Decimal = Field(..., ge=Decimal("0.00"), le=Decimal("100.00"), decimal_places=3)
    tenure_installments: int = Field(..., ge=1, le=600)
    emi_frequency: EmiFrequencyLiteral = "monthly"
    calculation_method: CalculationMethodLiteral = "reducing_balance"


class EmiScheduleRowResponse(BaseModel):
    installment_number: int
    due_date: dt.date
    opening_principal: Decimal
    emi_amount: Decimal
    principal_component: Decimal
    interest_component: Decimal
    closing_principal: Decimal
    is_final_adjustment: bool = False


class EmiCalculatorResponse(BaseModel):
    principal: Decimal
    annual_interest_rate: Decimal
    tenure_installments: int
    emi_frequency: str
    calculation_method: str
    periodic_emi: Decimal
    total_repayment: Decimal
    total_interest: Decimal
    principal_percentage: Decimal
    interest_percentage: Decimal
    assumptions: list[str]
    preview_schedule: list[EmiScheduleRowResponse] = []


class LoanCreateRequest(BaseModel):
    loan_name: str = Field(..., min_length=1, max_length=150)
    lender_name: str = Field(..., min_length=1, max_length=150)
    loan_type: LoanTypeLiteral = "personal"

    original_principal: Decimal | None = Field(None, gt=Decimal("0.00"), decimal_places=2)
    outstanding_principal: Decimal = Field(..., gt=Decimal("0.00"), decimal_places=2)
    interest_rate: Decimal = Field(..., ge=Decimal("0.00"), le=Decimal("100.00"), decimal_places=3)
    interest_rate_type: InterestRateTypeLiteral = "fixed"
    calculation_method: CalculationMethodLiteral = "reducing_balance"

    loan_start_date: dt.date
    tracking_start_date: dt.date
    first_emi_date: dt.date
    original_tenure_months: int | None = Field(None, ge=1, le=600)
    remaining_tenure_months: int = Field(..., ge=1, le=600)
    emi_amount: Decimal | None = Field(None, gt=Decimal("0.00"), decimal_places=2)
    emi_frequency: EmiFrequencyLiteral = "monthly"

    linked_repayment_account_id: uuid.UUID | None = None
    record_disbursement_to_account_id: uuid.UUID | None = None
    loan_reference: str | None = Field(None, max_length=100)
    processing_fee: Decimal | None = Field(None, ge=Decimal("0.00"), decimal_places=2)
    prepayment_charges_info: str | None = Field(None, max_length=255)
    notes: str | None = None

    reminder_enabled: bool = True
    reminder_days_before: list[int] = Field(default_factory=lambda: [5, 3, 1, 0])
    notification_channels: NotificationChannelsConfig = Field(
        default_factory=NotificationChannelsConfig
    )

    @model_validator(mode="after")
    def validate_loan_terms(self) -> "LoanCreateRequest":
        if not self.loan_name.strip() or not self.lender_name.strip():
            raise ValueError("Loan name and lender name cannot be blank.")
        if self.calculation_method != "zero_interest" and self.interest_rate == Decimal("0.000"):
            self.calculation_method = "zero_interest"
        if self.calculation_method == "zero_interest":
            self.interest_rate = Decimal("0.000")
        if (
            self.original_principal is not None
            and self.outstanding_principal > self.original_principal
        ):
            raise ValueError("Outstanding principal cannot exceed original principal.")
        if (
            self.original_tenure_months is not None
            and self.remaining_tenure_months > self.original_tenure_months
        ):
            raise ValueError("Remaining tenure cannot exceed original tenure.")
        cleaned = sorted({d for d in self.reminder_days_before if 0 <= d <= 60}, reverse=True)
        self.reminder_days_before = cleaned or [5, 3, 1, 0]
        return self


class LoanUpdateRequest(BaseModel):
    loan_name: str | None = Field(None, min_length=1, max_length=150)
    lender_name: str | None = Field(None, min_length=1, max_length=150)
    loan_type: LoanTypeLiteral | None = None
    linked_repayment_account_id: uuid.UUID | None = None
    loan_reference: str | None = Field(None, max_length=100)
    prepayment_charges_info: str | None = Field(None, max_length=255)
    notes: str | None = None
    reminder_enabled: bool | None = None
    reminder_days_before: list[int] | None = None
    notification_channels: NotificationChannelsConfig | None = None


class LoanInterestRateRevisionRequest(BaseModel):
    new_rate: Decimal = Field(..., ge=Decimal("0.00"), le=Decimal("100.00"), decimal_places=3)
    effective_date: dt.date
    policy: Literal["recalculate_emi", "adjust_tenure"] = "recalculate_emi"
    reason: str | None = Field(None, max_length=255)


class LoanPaymentCreateRequest(BaseModel):
    payment_type: Literal["emi", "partial", "prepayment", "foreclosure"] = "emi"
    payment_date: dt.date
    payment_account_id: uuid.UUID
    installment_id: uuid.UUID | None = None
    principal_paid: Decimal = Field(..., ge=Decimal("0.00"), decimal_places=2)
    interest_paid: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"), decimal_places=2)
    fee_paid: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"), decimal_places=2)
    prepayment_mode: Literal["reduce_tenure", "reduce_emi"] = "reduce_tenure"
    reference_number: str | None = Field(None, max_length=100)
    notes: str | None = None
    idempotency_key: str | None = Field(None, max_length=100)

    @model_validator(mode="after")
    def validate_amounts(self) -> "LoanPaymentCreateRequest":
        if (self.principal_paid + self.interest_paid) <= Decimal("0.00"):
            raise ValueError("Total principal + interest repayment must be positive.")
        return self


class LoanPaymentLinkRequest(BaseModel):
    transaction_id: uuid.UUID
    installment_id: uuid.UUID | None = None
    principal_component: Decimal = Field(..., ge=Decimal("0.00"), decimal_places=2)
    interest_component: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"), decimal_places=2)
    payment_type: Literal["emi", "partial", "prepayment", "foreclosure"] = "emi"
    notes: str | None = None


class LoanPaymentReverseRequest(BaseModel):
    reason: str = Field(..., min_length=2, max_length=255)


class LoanPrepaymentScenarioRequest(BaseModel):
    extra_monthly_emi: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"), decimal_places=2)
    lump_sum_prepayment: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"), decimal_places=2)
    prepayment_mode: Literal["reduce_tenure", "reduce_emi"] = "reduce_tenure"
    user_prepayment_fee: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"), decimal_places=2)


class LoanPrepaymentScenarioResponse(BaseModel):
    is_scenario_simulation: bool = True
    disclaimer: str
    current_outstanding_principal: Decimal
    baseline_emi: Decimal
    baseline_remaining_installments: int
    baseline_remaining_interest: Decimal
    baseline_payoff_date: dt.date | None = None

    scenario_revised_emi: Decimal
    scenario_remaining_installments: int
    scenario_remaining_interest: Decimal
    scenario_payoff_date: dt.date | None = None
    revised_principal_after_lump_sum: Decimal

    estimated_interest_saved: Decimal
    user_supplied_prepayment_fee: Decimal
    net_estimated_savings: Decimal
    tenure_months_saved: int


class LoanInstallmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    loan_id: uuid.UUID
    installment_number: int
    due_date: dt.date
    opening_principal: Decimal
    emi_amount: Decimal
    principal_component: Decimal
    interest_component: Decimal
    closing_principal: Decimal
    principal_paid: Decimal
    interest_paid: Decimal
    status: str
    derived_status: str = "upcoming"
    paid_date: dt.date | None = None
    is_final_adjustment: bool


class LoanInterestRateHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    loan_id: uuid.UUID
    previous_rate: Decimal | None = None
    new_rate: Decimal
    effective_date: dt.date
    previous_emi: Decimal | None = None
    new_emi: Decimal
    remaining_tenure_months: int
    reason: str | None = None
    created_at: dt.datetime


class LoanPaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    loan_id: uuid.UUID
    loan_name: str | None = None
    installment_id: uuid.UUID | None = None
    payment_account_id: uuid.UUID | None = None
    account_name: str | None = None
    principal_transfer_id: uuid.UUID | None = None
    interest_transaction_id: uuid.UUID | None = None
    fee_transaction_id: uuid.UUID | None = None
    linked_transaction_id: uuid.UUID | None = None
    payment_type: str
    payment_date: dt.date
    principal_paid: Decimal
    interest_paid: Decimal
    fee_paid: Decimal
    total_paid: Decimal
    reference_number: str | None = None
    payment_status: str
    reversal_reason: str | None = None
    notes: str | None = None
    created_at: dt.datetime


class LoanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    liability_account_id: uuid.UUID
    linked_repayment_account_id: uuid.UUID | None = None
    linked_repayment_account_name: str | None = None

    loan_name: str
    lender_name: str
    loan_type: str

    original_principal: Decimal | None = None
    outstanding_principal_at_start: Decimal
    current_outstanding_principal: Decimal
    currency: str

    interest_rate: Decimal
    interest_rate_type: str
    calculation_method: str

    loan_start_date: dt.date
    tracking_start_date: dt.date
    first_emi_date: dt.date
    next_emi_due_date: dt.date | None = None
    maturity_date: dt.date | None = None

    original_tenure_months: int | None = None
    remaining_tenure_months: int
    emi_amount: Decimal
    emi_frequency: str
    anchor_day: int

    loan_reference: str | None = None
    processing_fee: Decimal | None = None
    prepayment_charges_info: str | None = None
    notes: str | None = None
    status: str
    derived_status: str = "active"

    total_principal_repaid: Decimal = Decimal("0.00")
    total_interest_paid: Decimal = Decimal("0.00")
    total_paid_overall: Decimal = Decimal("0.00")
    repayment_progress_pct: Decimal = Decimal("0.00")
    overdue_installments_count: int = 0

    reminder_enabled: bool
    reminder_days_before: list[int]
    notification_channels: dict[str, bool]

    created_at: dt.datetime
    updated_at: dt.datetime

    installments: list[LoanInstallmentResponse] = []
    rate_history: list[LoanInterestRateHistoryResponse] = []
    payments: list[LoanPaymentResponse] = []
    reminders: list[BillReminderResponse] = []


class LoanListResponse(BaseModel):
    items: list[LoanResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class LoanPaymentListResponse(BaseModel):
    items: list[LoanPaymentResponse]
    total: int


class LoanOverviewResponse(BaseModel):
    active_loans_count: int
    closed_loans_count: int
    overdue_loans_count: int
    overdue_installments_count: int
    total_outstanding_principal: Decimal
    total_original_principal_known: Decimal | None = None
    total_monthly_emi_commitment: Decimal
    total_principal_repaid: Decimal
    total_interest_paid: Decimal
    next_emi_due_loan: LoanResponse | None = None


class LoanBreakdownItem(BaseModel):
    loan_id: uuid.UUID
    loan_name: str
    lender_name: str
    loan_type: str
    outstanding_principal: Decimal
    principal_repaid: Decimal
    interest_paid: Decimal
    emi_amount: Decimal
    progress_pct: Decimal
    maturity_date: dt.date | None = None
    status: str


class LoanAnalyticsResponse(BaseModel):
    total_outstanding_principal: Decimal
    total_principal_repaid: Decimal
    total_interest_paid: Decimal
    total_repayment_actual: Decimal
    projected_remaining_interest: Decimal
    monthly_emi_commitment: Decimal
    estimated_latest_maturity_date: dt.date | None = None
    principal_share_pct: Decimal
    interest_share_pct: Decimal
    by_loan: list[LoanBreakdownItem] = []
    repayment_trend: list[dict] = []
