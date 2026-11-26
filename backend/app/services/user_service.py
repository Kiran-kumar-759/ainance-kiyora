import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.assistant import AiConversation
from app.models.bills import Bill
from app.models.documents import FinancialDocument
from app.models.email_ingestion import EmailConnection
from app.models.finance import BankingConnection, FinancialAccount, FinancialTransaction
from app.models.forecasting import ForecastScenario
from app.models.loans import Loan
from app.models.subscriptions import Subscription
from app.models.user import User
from app.repositories.preference_repository import PreferenceRepository
from app.repositories.user_repository import UserRepository
from app.schemas.user import (
    PrivacyDataSummaryResponse,
    UserPreferenceResponse,
    UserPreferenceUpdateRequest,
    UserResponse,
    UserUpdateRequest,
)

DEFAULT_NOTIFICATION_PREFERENCES: dict[str, Any] = {
    "email_alerts": True,
    "bill_reminders": True,
    "subscription_reminders": True,
    "loan_emi_reminders": True,
    "payment_due_reminders": True,
    "financial_insights": True,
    "spending_anomalies": True,
    "forecast_notifications": True,
    "monthly_summary": True,
    "email_reminders_enabled": True,
    "sms_reminders_enabled": False,
    "phone_number": None,
    "number_format": "en-IN",
    "week_start": "monday",
    "language": "en-IN",
    "default_landing_view": "dashboard",
    "compact_sidebar": False,
}

_ALLOWED_LANDING_VIEWS = {"dashboard", "analytics", "assistant", "bills", "transactions"}
_ALLOWED_WEEK_STARTS = {"monday", "sunday"}


def merge_notification_preferences(
    existing: dict[str, Any] | None,
    updates: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge persisted user preference JSON with canonical defaults safely."""
    merged: dict[str, Any] = {**DEFAULT_NOTIFICATION_PREFERENCES, **(existing or {})}
    if updates:
        for key, val in updates.items():
            if key == "default_landing_view" and val not in _ALLOWED_LANDING_VIEWS:
                continue
            if key == "week_start" and val not in _ALLOWED_WEEK_STARTS:
                continue
            if key == "language" and val not in ("en-IN", "en-US"):
                continue
            merged[key] = val
    return merged


class UserService:
    """Service handling user profile, settings persistence, and privacy summary with strict isolation."""

    def __init__(
        self,
        user_repo: UserRepository | None = None,
        pref_repo: PreferenceRepository | None = None,
    ):
        self.user_repo = user_repo or UserRepository()
        self.pref_repo = pref_repo or PreferenceRepository()

    def get_profile(self, user: User) -> UserResponse:
        return UserResponse.model_validate(user)

    def update_profile(
        self,
        db: Session,
        user: User,
        req: UserUpdateRequest,
    ) -> UserResponse:
        updated_user = self.user_repo.update(db, user, full_name=req.full_name.strip())
        return UserResponse.model_validate(updated_user)

    def get_preferences(
        self,
        db: Session,
        user_id: uuid.UUID,
    ) -> UserPreferenceResponse:
        pref = self.pref_repo.get_by_user_id(db, user_id)
        if not pref:
            pref = self.pref_repo.create_defaults(db, user_id)
        resp = UserPreferenceResponse.model_validate(pref)
        resp.notification_preferences = merge_notification_preferences(pref.notification_preferences)
        return resp

    def update_preferences(
        self,
        db: Session,
        user_id: uuid.UUID,
        req: UserPreferenceUpdateRequest,
    ) -> UserPreferenceResponse:
        pref = self.pref_repo.get_by_user_id(db, user_id)
        if not pref:
            pref = self.pref_repo.create_defaults(db, user_id)

        update_data = req.model_dump(exclude_unset=True)
        if "notification_preferences" in update_data:
            update_data["notification_preferences"] = merge_notification_preferences(
                pref.notification_preferences,
                update_data.get("notification_preferences"),
            )
            if "locale" in update_data and "number_format" not in (req.notification_preferences or {}):
                update_data["notification_preferences"]["number_format"] = update_data["locale"]
        elif "locale" in update_data:
            update_data["notification_preferences"] = merge_notification_preferences(
                pref.notification_preferences,
                {"number_format": update_data["locale"]},
            )

        updated_pref = self.pref_repo.update(db, pref, **update_data)
        resp = UserPreferenceResponse.model_validate(updated_pref)
        resp.notification_preferences = merge_notification_preferences(updated_pref.notification_preferences)
        return resp

    def get_privacy_summary(self, db: Session, user: User) -> PrivacyDataSummaryResponse:
        uid = user.id

        def _count(model) -> int:
            return int(db.execute(select(func.count(model.id)).where(model.user_id == uid)).scalar_one() or 0)

        return PrivacyDataSummaryResponse(
            accounts_count=_count(FinancialAccount),
            transactions_count=_count(FinancialTransaction),
            bills_count=_count(Bill),
            subscriptions_count=_count(Subscription),
            loans_count=_count(Loan),
            documents_count=_count(FinancialDocument),
            conversations_count=_count(AiConversation),
            forecast_scenarios_count=_count(ForecastScenario),
            banking_connections_count=_count(BankingConnection),
            email_connections_count=_count(EmailConnection),
            data_storage_disclosures=[
                "Financial accounts, double-entry ledger journals, transactions, bills, subscriptions, loans, and forecasts are stored privately in PostgreSQL scoped strictly to your user ID.",
                "Uploaded PDFs and images are stored on private server storage with UUID keys and SHA-256 checksums, never exposed publicly without an authenticated session.",
                "Connected Gmail access uses read-only OAuth scopes with Fernet-encrypted tokens stored server-side; disconnecting revokes tokens while preserving verified financial ledger history.",
                "Optional AI enrichment (Groq) and external web research providers (Tavily, LangSearch, Firecrawl) receive sanitized, non-sensitive prompts; API keys remain strictly server-side.",
            ],
            export_endpoints=[
                {
                    "label": "Transactions Ledger CSV",
                    "endpoint": "/api/v1/reports/transactions.csv",
                    "description": "Exports formula-safe CSV of your financial transactions.",
                },
                {
                    "label": "Category Spend Breakdown CSV",
                    "endpoint": "/api/v1/reports/category-breakdown.csv",
                    "description": "Exports category-level expenses and shares in INR.",
                },
                {
                    "label": "Monthly Cash-Flow Summary CSV",
                    "endpoint": "/api/v1/reports/monthly-summary.csv",
                    "description": "Exports monthly income, expenses, and net savings.",
                },
            ],
            account_deletion_status="deferred",
            account_deletion_note=(
                "Self-service destructive account deletion is deferred to ensure complete dependency-safe "
                "purge across double-entry ledger journals, uploaded files, OAuth revocations, and audit logs "
                "plus pre-deletion archive verification. You can revoke active sessions or disconnect email/bank integrations at any time."
            ),
        )
