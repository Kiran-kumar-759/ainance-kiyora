import datetime as dt
import math
import uuid
from collections import defaultdict
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.bills import Notification
from app.models.finance import FinancialAccount, FinancialTransaction
from app.models.subscriptions import (
    Subscription,
    SubscriptionPayment,
    SubscriptionPriceHistory,
)
from app.models.user import User
from app.repositories.bills.bill_repository import BillRepository
from app.repositories.finance.account_repository import AccountRepository
from app.repositories.finance.category_repository import CategoryRepository
from app.repositories.finance.transaction_repository import TransactionRepository
from app.repositories.subscriptions.subscription_repository import SubscriptionRepository
from app.schemas.bills import BillReminderResponse
from app.schemas.finance.transaction import TransactionCreateRequest
from app.schemas.subscriptions import (
    CategoryBreakdownItem,
    MonthlySpendPoint,
    SubscriptionAnalyticsResponse,
    SubscriptionCancelRequest,
    SubscriptionCandidateActionRequest,
    SubscriptionCandidateResponse,
    SubscriptionCreateRequest,
    SubscriptionListResponse,
    SubscriptionOverviewResponse,
    SubscriptionPaymentCreateRequest,
    SubscriptionPaymentLinkRequest,
    SubscriptionPaymentListResponse,
    SubscriptionPaymentResponse,
    SubscriptionPaymentReverseRequest,
    SubscriptionPriceChangeRequest,
    SubscriptionPriceHistoryResponse,
    SubscriptionReminderUpdateRequest,
    SubscriptionResponse,
    SubscriptionUpdateRequest,
)
from app.services.bills.reminder_service import ReminderService
from app.services.bills.status_engine import resolve_user_today
from app.services.finance.category_service import CategoryService
from app.services.finance.ledger_service import LedgerService
from app.services.finance.transaction_service import TransactionService
from app.services.subscriptions.subscription_math import (
    advance_subscription_renewal,
    compute_monthly_and_annual_equivalent,
    detect_subscription_candidates,
    quantize_inr,
)

DUE_SOON_DAYS = 7


class SubscriptionService:
    """
    Service managing OTT & recurring subscriptions, renewal tracking,
    price history, atomic ledger-integrated payments, analytics, and candidates.
    """

    def __init__(self):
        self.sub_repo = SubscriptionRepository()
        self.bill_repo = BillRepository()
        self.account_repo = AccountRepository()
        self.category_repo = CategoryRepository()
        self.category_service = CategoryService()
        self.transaction_repo = TransactionRepository()
        self.transaction_service = TransactionService()
        self.ledger_service = LedgerService()
        self.reminder_service = ReminderService()

    def _user_tz(self, user: User) -> str:
        return (
            user.preferences.timezone
            if user.preferences and user.preferences.timezone
            else "Asia/Kolkata"
        )

    def _resolve_category_id(
        self, db: Session, user: User, explicit_category_id: uuid.UUID | None
    ) -> uuid.UUID | None:
        if explicit_category_id is not None:
            cat = self.category_repo.get_by_id(db, explicit_category_id, user.id)
            if not cat:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Specified financial category was not found.",
                )
            return cat.id
        self.category_service.seed_default_categories(db, commit=False)
        cat = self.category_repo.get_system_category_by_name(db, "Subscriptions", "expense")
        return cat.id if cat else None

    def _validate_account(
        self, db: Session, user: User, account_id: uuid.UUID | None
    ) -> FinancialAccount | None:
        if account_id is None:
            return None
        acc = self.account_repo.get_by_id(db, account_id, user.id)
        if not acc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Financial account not found."
            )
        if acc.status != "active":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Linked financial account is archived.",
            )
        return acc

    def _payment_to_response(self, p: SubscriptionPayment) -> SubscriptionPaymentResponse:
        return SubscriptionPaymentResponse(
            id=p.id,
            user_id=p.user_id,
            subscription_id=p.subscription_id,
            subscription_name=p.subscription.subscription_name if p.subscription else None,
            financial_account_id=p.financial_account_id,
            account_name=p.financial_account.name if p.financial_account else None,
            transaction_id=p.transaction_id,
            transfer_id=p.transfer_id,
            amount_paid=p.amount_paid,
            currency=p.currency,
            payment_date=p.payment_date,
            payment_method=p.payment_method,
            reference_number=p.reference_number,
            payment_status=p.payment_status,
            reversal_reason=p.reversal_reason,
            notes=p.notes,
            created_at=p.created_at,
        )

    def _to_response(self, sub: Subscription, user_today: dt.date) -> SubscriptionResponse:
        monthly_eq, annual_eq = compute_monthly_and_annual_equivalent(
            sub.amount, sub.billing_frequency, sub.custom_interval_days
        )
        days_until = (
            (sub.next_renewal_date - user_today).days
            if sub.next_renewal_date is not None
            else None
        )
        is_active_or_trial = sub.status in {"active", "trial"}
        is_renewal_due_soon = bool(
            is_active_or_trial and days_until is not None and 0 <= days_until <= DUE_SOON_DAYS
        )
        is_trial_ending_soon = bool(
            sub.status == "trial"
            and sub.trial_end_date is not None
            and 0 <= (sub.trial_end_date - user_today).days <= DUE_SOON_DAYS
        )
        completed_payments = [p for p in (sub.payments or []) if p.payment_status == "completed"]
        total_actual_paid = quantize_inr(
            sum((Decimal(p.amount_paid) for p in completed_payments), Decimal("0.00"))
        )

        return SubscriptionResponse(
            id=sub.id,
            user_id=sub.user_id,
            financial_category_id=sub.financial_category_id,
            financial_category_name=(
                sub.financial_category.name if sub.financial_category else None
            ),
            linked_account_id=sub.linked_account_id,
            linked_account_name=sub.linked_account.name if sub.linked_account else None,
            subscription_name=sub.subscription_name,
            provider_name=sub.provider_name,
            category=sub.category,
            plan_name=sub.plan_name,
            description=sub.description,
            notes=sub.notes,
            amount=sub.amount,
            monthly_equivalent=monthly_eq,
            annual_equivalent=annual_eq,
            is_amount_unknown=sub.amount is None,
            currency=sub.currency,
            billing_frequency=sub.billing_frequency,
            custom_interval_days=sub.custom_interval_days,
            anchor_day=sub.anchor_day,
            start_date=sub.start_date,
            next_renewal_date=sub.next_renewal_date,
            previous_renewal_date=sub.previous_renewal_date,
            trial_start_date=sub.trial_start_date,
            trial_end_date=sub.trial_end_date,
            cancellation_date=sub.cancellation_date,
            days_until_renewal=days_until,
            is_renewal_due_soon=is_renewal_due_soon,
            is_trial_ending_soon=is_trial_ending_soon,
            preferred_payment_method=sub.preferred_payment_method,
            status=sub.status,
            reminder_enabled=sub.reminder_enabled,
            reminder_days_before=list(sub.reminder_days_before or []),
            notification_channels=dict(sub.notification_channels or {}),
            total_actual_paid=total_actual_paid,
            created_at=sub.created_at,
            updated_at=sub.updated_at,
            price_history=[
                SubscriptionPriceHistoryResponse.model_validate(h)
                for h in (sub.price_history or [])
            ],
            payments=[self._payment_to_response(p) for p in (sub.payments or [])],
            reminders=[BillReminderResponse.model_validate(r) for r in (sub.reminders or [])],
        )

    def create_subscription(
        self, db: Session, user: User, req: SubscriptionCreateRequest
    ) -> SubscriptionResponse:
        tz = self._user_tz(user)
        user_today = resolve_user_today(tz)
        cat_id = self._resolve_category_id(db, user, req.financial_category_id)
        self._validate_account(db, user, req.linked_account_id)

        anchor_day = req.next_renewal_date.day if req.next_renewal_date else req.start_date.day
        next_renewal = req.next_renewal_date
        if next_renewal is None:
            if req.is_trial and req.trial_end_date is not None:
                next_renewal = req.trial_end_date
            else:
                next_renewal = advance_subscription_renewal(
                    req.start_date,
                    req.billing_frequency,
                    anchor_day=anchor_day,
                    custom_interval_days=req.custom_interval_days,
                )

        initial_status = "trial" if (req.is_trial or req.trial_end_date is not None) else "active"

        try:
            sub = Subscription(
                user_id=user.id,
                financial_category_id=cat_id,
                linked_account_id=req.linked_account_id,
                subscription_name=req.subscription_name.strip(),
                provider_name=req.provider_name.strip() if req.provider_name else None,
                category=req.category,
                plan_name=req.plan_name.strip() if req.plan_name else None,
                description=req.description.strip() if req.description else None,
                notes=req.notes.strip() if req.notes else None,
                amount=req.amount,
                currency=req.currency.upper(),
                billing_frequency=req.billing_frequency,
                custom_interval_days=req.custom_interval_days,
                anchor_day=anchor_day,
                start_date=req.start_date,
                next_renewal_date=next_renewal,
                previous_renewal_date=req.previous_renewal_date,
                trial_start_date=req.trial_start_date,
                trial_end_date=req.trial_end_date,
                preferred_payment_method=req.preferred_payment_method,
                status=initial_status,
                reminder_enabled=req.reminder_enabled,
                reminder_days_before=req.reminder_days_before,
                notification_channels=req.notification_channels.model_dump(),
            )
            self.sub_repo.create(db, sub)

            if req.amount is not None:
                self.sub_repo.add_price_history(
                    db,
                    SubscriptionPriceHistory(
                        user_id=user.id,
                        subscription_id=sub.id,
                        previous_price=None,
                        new_price=req.amount,
                        effective_date=req.start_date,
                        reason="Initial subscription price",
                    ),
                )

            self.reminder_service.sync_reminders_for_subscription(db, sub, user_timezone=tz)
            db.commit()
            loaded = self.sub_repo.get_by_id(db, sub.id, user.id)
            assert loaded is not None
            return self._to_response(loaded, user_today)
        except Exception:
            db.rollback()
            raise

    def list_subscriptions(
        self,
        db: Session,
        user: User,
        status_filter: str | None = None,
        category: str | None = None,
        search: str | None = None,
        sort_by: str = "next_renewal_asc",
        include_archived: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> SubscriptionListResponse:
        user_today = resolve_user_today(self._user_tz(user))
        raw = self.sub_repo.list_by_user(
            db,
            user.id,
            include_archived=include_archived,
            category=category,
            status_filter=status_filter,
            search=search,
        )
        items = [self._to_response(s, user_today) for s in raw]

        if sort_by == "next_renewal_desc":
            items.sort(key=lambda s: s.next_renewal_date or dt.date.min, reverse=True)
        elif sort_by == "cost_desc":
            items.sort(key=lambda s: s.monthly_equivalent or Decimal("0.00"), reverse=True)
        elif sort_by == "cost_asc":
            items.sort(key=lambda s: s.monthly_equivalent or Decimal("0.00"))
        elif sort_by == "name_asc":
            items.sort(key=lambda s: s.subscription_name.lower())
        else:
            items.sort(key=lambda s: s.next_renewal_date or dt.date.max)

        total = len(items)
        total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
        offset = max(0, (page - 1) * page_size)
        return SubscriptionListResponse(
            items=items[offset : offset + page_size],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    def get_subscription(
        self, db: Session, user: User, sub_id: uuid.UUID
    ) -> SubscriptionResponse:
        sub = self.sub_repo.get_by_id(db, sub_id, user.id)
        if not sub:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found."
            )
        return self._to_response(sub, resolve_user_today(self._user_tz(user)))

    def update_subscription(
        self, db: Session, user: User, sub_id: uuid.UUID, req: SubscriptionUpdateRequest
    ) -> SubscriptionResponse:
        sub = self.sub_repo.get_by_id(db, sub_id, user.id)
        if not sub:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found."
            )
        if sub.status == "archived":
            raise HTTPException(status_code=400, detail="Archived subscriptions cannot be edited.")

        tz = self._user_tz(user)
        user_today = resolve_user_today(tz)

        if req.subscription_name is not None:
            stripped = req.subscription_name.strip()
            if not stripped:
                raise HTTPException(status_code=400, detail="Subscription name cannot be blank.")
            sub.subscription_name = stripped
        if req.provider_name is not None:
            sub.provider_name = req.provider_name.strip() or None
        if req.category is not None:
            sub.category = req.category
        if req.plan_name is not None:
            sub.plan_name = req.plan_name.strip() or None
        if req.description is not None:
            sub.description = req.description.strip() or None
        if req.notes is not None:
            sub.notes = req.notes.strip() or None
        if req.billing_frequency is not None:
            sub.billing_frequency = req.billing_frequency
        if req.custom_interval_days is not None:
            sub.custom_interval_days = req.custom_interval_days
        if sub.billing_frequency == "custom" and not sub.custom_interval_days:
            raise HTTPException(
                status_code=400, detail="Custom frequency requires custom_interval_days."
            )
        if req.next_renewal_date is not None:
            sub.next_renewal_date = req.next_renewal_date
            sub.anchor_day = req.next_renewal_date.day
        if req.trial_end_date is not None:
            sub.trial_end_date = req.trial_end_date
        if req.financial_category_id is not None:
            sub.financial_category_id = self._resolve_category_id(db, user, req.financial_category_id)
        if req.linked_account_id is not None:
            self._validate_account(db, user, req.linked_account_id)
            sub.linked_account_id = req.linked_account_id
        if req.preferred_payment_method is not None:
            sub.preferred_payment_method = req.preferred_payment_method
        if req.reminder_enabled is not None:
            sub.reminder_enabled = req.reminder_enabled
        if req.reminder_days_before is not None:
            sub.reminder_days_before = sorted(
                {d for d in req.reminder_days_before if 0 <= d <= 60}, reverse=True
            ) or [7, 3, 1, 0]
        if req.notification_channels is not None:
            sub.notification_channels = req.notification_channels.model_dump()

        if req.amount is not None and req.amount != sub.amount:
            self.sub_repo.add_price_history(
                db,
                SubscriptionPriceHistory(
                    user_id=user.id,
                    subscription_id=sub.id,
                    previous_price=sub.amount,
                    new_price=req.amount,
                    effective_date=user_today,
                    reason=req.price_change_reason or "Subscription price updated",
                ),
            )
            sub.amount = req.amount

        db.add(sub)
        db.flush()
        self.reminder_service.sync_reminders_for_subscription(db, sub, user_timezone=tz)
        db.commit()
        db.expire_all()
        return self.get_subscription(db, user, sub.id)

    def record_price_change(
        self, db: Session, user: User, sub_id: uuid.UUID, req: SubscriptionPriceChangeRequest
    ) -> SubscriptionResponse:
        sub = self.sub_repo.get_by_id(db, sub_id, user.id)
        if not sub:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found."
            )
        if sub.status == "archived":
            raise HTTPException(status_code=400, detail="Cannot change price on archived subscription.")

        self.sub_repo.add_price_history(
            db,
            SubscriptionPriceHistory(
                user_id=user.id,
                subscription_id=sub.id,
                previous_price=sub.amount,
                new_price=req.new_price,
                effective_date=req.effective_date,
                reason=req.reason.strip() if req.reason else None,
            ),
        )
        sub.amount = req.new_price
        db.add(sub)
        db.commit()
        db.expire_all()
        return self.get_subscription(db, user, sub.id)

    def _set_lifecycle_status(
        self,
        db: Session,
        user: User,
        sub_id: uuid.UUID,
        new_status: str,
        cancellation_date: dt.date | None = None,
    ) -> SubscriptionResponse:
        sub = self.sub_repo.get_by_id(db, sub_id, user.id)
        if not sub:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found."
            )
        tz = self._user_tz(user)
        user_today = resolve_user_today(tz)

        if new_status == "paused" and sub.status not in {"active", "trial"}:
            raise HTTPException(status_code=400, detail="Only active or trial subscriptions can be paused.")
        if new_status == "active" and sub.status == "archived":
            raise HTTPException(status_code=400, detail="Archived subscriptions cannot be resumed.")
        if new_status == "cancelled":
            sub.cancellation_date = cancellation_date or user_today
            sub.reminder_enabled = False
        elif new_status == "active" and sub.status == "cancelled":
            sub.cancellation_date = None
            sub.reminder_enabled = True

        sub.status = new_status
        db.add(sub)
        self.reminder_service.sync_reminders_for_subscription(db, sub, user_timezone=tz)
        db.commit()
        db.expire_all()
        return self.get_subscription(db, user, sub.id)

    def pause_subscription(self, db: Session, user: User, sub_id: uuid.UUID) -> SubscriptionResponse:
        return self._set_lifecycle_status(db, user, sub_id, "paused")

    def resume_subscription(self, db: Session, user: User, sub_id: uuid.UUID) -> SubscriptionResponse:
        return self._set_lifecycle_status(db, user, sub_id, "active")

    def cancel_subscription(
        self, db: Session, user: User, sub_id: uuid.UUID, req: SubscriptionCancelRequest | None = None
    ) -> SubscriptionResponse:
        return self._set_lifecycle_status(
            db, user, sub_id, "cancelled", cancellation_date=req.cancellation_date if req else None
        )

    def archive_subscription(
        self, db: Session, user: User, sub_id: uuid.UUID
    ) -> SubscriptionResponse:
        return self._set_lifecycle_status(db, user, sub_id, "archived")

    def update_reminders(
        self, db: Session, user: User, sub_id: uuid.UUID, req: SubscriptionReminderUpdateRequest
    ) -> SubscriptionResponse:
        sub = self.sub_repo.get_by_id(db, sub_id, user.id)
        if not sub:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found."
            )
        if req.reminder_enabled is not None:
            sub.reminder_enabled = req.reminder_enabled
        if req.reminder_days_before is not None:
            sub.reminder_days_before = sorted(
                {d for d in req.reminder_days_before if 0 <= d <= 60}, reverse=True
            ) or [7, 3, 1, 0]
        if req.notification_channels is not None:
            sub.notification_channels = req.notification_channels.model_dump()
        db.add(sub)
        self.reminder_service.sync_reminders_for_subscription(
            db, sub, user_timezone=self._user_tz(user)
        )
        db.commit()
        db.expire_all()
        return self.get_subscription(db, user, sub.id)

    def advance_renewal(self, db: Session, user: User, sub_id: uuid.UUID) -> SubscriptionResponse:
        sub = self.sub_repo.get_by_id(db, sub_id, user.id)
        if not sub:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found."
            )
        if sub.status in {"cancelled", "archived"}:
            raise HTTPException(
                status_code=400, detail="Cannot advance renewal on cancelled/archived subscription."
            )
        tz = self._user_tz(user)
        base = sub.next_renewal_date or resolve_user_today(tz)
        sub.previous_renewal_date = base
        sub.next_renewal_date = advance_subscription_renewal(
            base,
            sub.billing_frequency,
            anchor_day=sub.anchor_day,
            custom_interval_days=sub.custom_interval_days,
        )
        if sub.status == "trial":
            sub.status = "active"
        db.add(sub)
        self.reminder_service.sync_reminders_for_subscription(db, sub, user_timezone=tz)
        db.commit()
        db.expire_all()
        return self.get_subscription(db, user, sub.id)

    def record_payment(
        self,
        db: Session,
        user: User,
        sub_id: uuid.UUID,
        req: SubscriptionPaymentCreateRequest,
    ) -> SubscriptionResponse:
        if req.idempotency_key:
            dup = self.sub_repo.get_payment_by_idempotency(
                db, user.id, sub_id, req.idempotency_key
            )
            if dup:
                return self.get_subscription(db, user, sub_id)

        sub = self.sub_repo.get_for_update(db, sub_id, user.id)
        if not sub:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found."
            )
        if sub.status == "archived":
            raise HTTPException(
                status_code=400, detail="Cannot record payments on an archived subscription."
            )

        account = self.account_repo.get_by_id(db, req.financial_account_id, user.id)
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Payment account not found."
            )
        if account.status != "active":
            raise HTTPException(status_code=400, detail="Cannot pay from an archived account.")
        if account.account_type in {"loan_liability"}:
            raise HTTPException(
                status_code=400, detail="Cannot pay a subscription from a loan liability account."
            )
        if account.account_type != "credit_card" and req.amount_paid > account.current_balance:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Insufficient balance in '{account.name}'. Available: "
                    f"₹{account.current_balance:,.2f}, required: ₹{req.amount_paid:,.2f}."
                ),
            )

        tz = self._user_tz(user)
        try:
            cat_id = sub.financial_category_id or self._resolve_category_id(db, user, None)
            tx_req = TransactionCreateRequest(
                account_id=account.id,
                transaction_type="expense",
                amount=req.amount_paid,
                currency=sub.currency,
                category_id=cat_id,
                description=f"Subscription Payment: {sub.subscription_name}",
                merchant_payee=sub.provider_name or sub.subscription_name,
                transaction_date=req.payment_date,
                notes=req.notes or f"Recorded via {req.payment_method.upper()}",
            )
            created_tx = self.transaction_service.create_transaction(
                db=db,
                user=user,
                req=tx_req,
                source="subscription_payment",
                commit=False,
            )

            db.refresh(account)
            if account.account_type != "credit_card" and account.current_balance < Decimal("0.00"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Payment would make '{account.name}' balance negative.",
                )

            payment = SubscriptionPayment(
                user_id=user.id,
                subscription_id=sub.id,
                financial_account_id=account.id,
                transaction_id=created_tx.id,
                amount_paid=req.amount_paid,
                currency=sub.currency,
                payment_date=req.payment_date,
                payment_method=req.payment_method,
                reference_number=req.reference_number.strip() if req.reference_number else None,
                payment_status="completed",
                notes=req.notes.strip() if req.notes else None,
                idempotency_key=req.idempotency_key,
            )
            self.sub_repo.create_payment(db, payment)

            if req.advance_renewal_date and sub.status in {"active", "trial"}:
                base_due = sub.next_renewal_date or req.payment_date
                sub.previous_renewal_date = req.payment_date
                sub.next_renewal_date = advance_subscription_renewal(
                    base_due,
                    sub.billing_frequency,
                    anchor_day=sub.anchor_day,
                    custom_interval_days=sub.custom_interval_days,
                )
                if sub.status == "trial":
                    sub.status = "active"
                db.add(sub)
                self.reminder_service.sync_reminders_for_subscription(db, sub, user_timezone=tz)

            self.bill_repo.create_notification(
                db,
                Notification(
                    user_id=user.id,
                    title=f"Subscription Paid: {sub.subscription_name}",
                    message=(
                        f"Recorded subscription payment of ₹{req.amount_paid:,.2f} for "
                        f"{sub.subscription_name} on {req.payment_date.strftime('%d/%m/%Y')}."
                    ),
                    notification_type="subscription_paid",
                    related_subscription_id=sub.id,
                    dedupe_key=f"sub-paid:{payment.id}",
                ),
            )
            db.commit()
            return self.get_subscription(db, user, sub.id)
        except Exception:
            db.rollback()
            raise

    def link_existing_transaction(
        self,
        db: Session,
        user: User,
        sub_id: uuid.UUID,
        req: SubscriptionPaymentLinkRequest,
    ) -> SubscriptionResponse:
        sub = self.sub_repo.get_for_update(db, sub_id, user.id)
        if not sub:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found."
            )
        tx = self.transaction_repo.get_by_id(db, req.transaction_id, user.id)
        if not tx:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Financial transaction not found."
            )
        if tx.transaction_type != "expense":
            raise HTTPException(
                status_code=400, detail="Only expense transactions can link as subscription payments."
            )
        if self.sub_repo.get_payment_by_transaction(db, tx.id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This financial transaction is already linked to a subscription payment.",
            )

        tz = self._user_tz(user)
        try:
            payment = SubscriptionPayment(
                user_id=user.id,
                subscription_id=sub.id,
                financial_account_id=tx.account_id,
                transaction_id=tx.id,
                amount_paid=tx.amount,
                currency=tx.currency,
                payment_date=tx.transaction_date,
                payment_method=req.payment_method,
                reference_number=tx.external_reference,
                payment_status="completed",
                notes=req.notes or f"Linked transaction: {tx.description}",
            )
            self.sub_repo.create_payment(db, payment)

            if req.advance_renewal_date and sub.status in {"active", "trial"}:
                base_due = sub.next_renewal_date or tx.transaction_date
                sub.previous_renewal_date = tx.transaction_date
                sub.next_renewal_date = advance_subscription_renewal(
                    base_due,
                    sub.billing_frequency,
                    anchor_day=sub.anchor_day,
                    custom_interval_days=sub.custom_interval_days,
                )
                if sub.status == "trial":
                    sub.status = "active"
                db.add(sub)
                self.reminder_service.sync_reminders_for_subscription(db, sub, user_timezone=tz)

            db.commit()
            return self.get_subscription(db, user, sub.id)
        except Exception:
            db.rollback()
            raise

    def reverse_payment(
        self,
        db: Session,
        user: User,
        sub_id: uuid.UUID,
        payment_id: uuid.UUID,
        req: SubscriptionPaymentReverseRequest,
    ) -> SubscriptionResponse:
        payment = self.sub_repo.get_payment_by_id(db, payment_id, sub_id, user.id)
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Subscription payment not found."
            )
        if payment.payment_status == "reversed":
            raise HTTPException(status_code=400, detail="Payment has already been reversed.")

        try:
            if payment.transaction_id and payment.financial_account_id:
                acc = self.account_repo.get_by_id(db, payment.financial_account_id, user.id)
                if acc:
                    self.ledger_service.reverse_transaction_journal(
                        db, payment.transaction_id, acc.id, acc.account_type
                    )
            payment.payment_status = "reversed"
            payment.reversal_reason = req.reason.strip()
            db.add(payment)
            db.commit()
            return self.get_subscription(db, user, sub_id)
        except Exception:
            db.rollback()
            raise

    def list_payments(
        self, db: Session, user: User, subscription_id: uuid.UUID | None = None
    ) -> SubscriptionPaymentListResponse:
        if subscription_id is not None:
            sub = self.sub_repo.get_by_id(db, subscription_id, user.id)
            if not sub:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found."
                )
        rows = self.sub_repo.list_payments(db, user.id, subscription_id=subscription_id)
        return SubscriptionPaymentListResponse(
            items=[self._payment_to_response(p) for p in rows],
            total=len(rows),
        )

    def get_overview(self, db: Session, user: User) -> SubscriptionOverviewResponse:
        user_today = resolve_user_today(self._user_tz(user))
        raw = self.sub_repo.list_by_user(db, user.id, include_archived=True)
        subs = [self._to_response(s, user_today) for s in raw]

        active = [s for s in subs if s.status == "active"]
        trial = [s for s in subs if s.status == "trial"]
        paused = [s for s in subs if s.status == "paused"]
        cancelled = [s for s in subs if s.status == "cancelled"]
        archived = [s for s in subs if s.status == "archived"]

        active_or_trial = [s for s in subs if s.status in {"active", "trial"}]
        # Only active paid subscriptions count toward ongoing active recurring projections
        # Trials are separated unless they carry an active recurring price; let's include active only in recurring cost projection, and exclude paused/cancelled/archived!
        monthly_cost = quantize_inr(
            sum(
                (s.monthly_equivalent for s in active if s.monthly_equivalent is not None),
                Decimal("0.00"),
            )
        )
        annual_cost = quantize_inr(
            sum(
                (s.annual_equivalent for s in active if s.annual_equivalent is not None),
                Decimal("0.00"),
            )
        )

        payments = self.sub_repo.list_payments(db, user.id, limit=500)
        completed = [p for p in payments if p.payment_status == "completed"]
        actual_this_month = quantize_inr(
            sum(
                (
                    Decimal(p.amount_paid)
                    for p in completed
                    if p.payment_date.year == user_today.year
                    and p.payment_date.month == user_today.month
                ),
                Decimal("0.00"),
            )
        )
        actual_total = quantize_inr(
            sum((Decimal(p.amount_paid) for p in completed), Decimal("0.00"))
        )

        upcoming_sorted = sorted(
            [s for s in active_or_trial if s.next_renewal_date is not None],
            key=lambda s: s.next_renewal_date or dt.date.max,
        )
        return SubscriptionOverviewResponse(
            active_count=len(active),
            trial_count=len(trial),
            paused_count=len(paused),
            cancelled_count=len(cancelled),
            archived_count=len(archived),
            renewals_due_soon_count=sum(1 for s in active_or_trial if s.is_renewal_due_soon),
            trials_ending_soon_count=sum(1 for s in trial if s.is_trial_ending_soon),
            unknown_price_active_count=sum(1 for s in active if s.is_amount_unknown),
            monthly_recurring_cost=monthly_cost,
            annual_recurring_cost=annual_cost,
            actual_spent_this_month=actual_this_month,
            actual_spent_total=actual_total,
            next_renewal_subscription=upcoming_sorted[0] if upcoming_sorted else None,
            due_soon_threshold_days=DUE_SOON_DAYS,
        )

    def get_analytics(self, db: Session, user: User) -> SubscriptionAnalyticsResponse:
        user_today = resolve_user_today(self._user_tz(user))
        raw = self.sub_repo.list_by_user(db, user.id, include_archived=True)
        subs = [self._to_response(s, user_today) for s in raw]
        active = [s for s in subs if s.status == "active"]
        cancelled = [s for s in subs if s.status == "cancelled"]

        monthly_cost = quantize_inr(
            sum(
                (s.monthly_equivalent for s in active if s.monthly_equivalent is not None),
                Decimal("0.00"),
            )
        )
        annual_cost = quantize_inr(
            sum(
                (s.annual_equivalent for s in active if s.annual_equivalent is not None),
                Decimal("0.00"),
            )
        )

        cat_agg: dict[str, dict] = defaultdict(
            lambda: {
                "monthly": Decimal("0.00"),
                "annual": Decimal("0.00"),
                "actual": Decimal("0.00"),
                "count": 0,
            }
        )
        prov_agg: dict[str, dict] = defaultdict(
            lambda: {
                "monthly": Decimal("0.00"),
                "annual": Decimal("0.00"),
                "actual": Decimal("0.00"),
                "count": 0,
            }
        )
        monthly_trend_map: dict[str, dict] = defaultdict(
            lambda: {"actual": Decimal("0.00"), "count": 0}
        )

        total_actual = Decimal("0.00")
        price_changes: list[SubscriptionPriceHistoryResponse] = []
        price_increase_count = 0

        for s in subs:
            prov_key = s.provider_name or s.subscription_name
            if s.status == "active":
                cat_agg[s.category]["count"] += 1
                prov_agg[prov_key]["count"] += 1
                if s.monthly_equivalent is not None:
                    cat_agg[s.category]["monthly"] += s.monthly_equivalent
                    prov_agg[prov_key]["monthly"] += s.monthly_equivalent
                if s.annual_equivalent is not None:
                    cat_agg[s.category]["annual"] += s.annual_equivalent
                    prov_agg[prov_key]["annual"] += s.annual_equivalent

            for p in s.payments:
                if p.payment_status != "completed":
                    continue
                amt = Decimal(p.amount_paid)
                total_actual += amt
                cat_agg[s.category]["actual"] += amt
                prov_agg[prov_key]["actual"] += amt
                ym = p.payment_date.strftime("%Y-%m")
                monthly_trend_map[ym]["actual"] += amt
                monthly_trend_map[ym]["count"] += 1

            for h in s.price_history:
                price_changes.append(h)
                if h.previous_price is not None and Decimal(h.new_price) > Decimal(h.previous_price):
                    price_increase_count += 1

        by_cat = [
            CategoryBreakdownItem(
                name=k,
                monthly_projected=quantize_inr(v["monthly"]),
                annual_projected=quantize_inr(v["annual"]),
                actual_spent=quantize_inr(v["actual"]),
                count=v["count"],
            )
            for k, v in sorted(cat_agg.items(), key=lambda kv: kv[1]["monthly"], reverse=True)
        ]
        by_prov = [
            CategoryBreakdownItem(
                name=k,
                monthly_projected=quantize_inr(v["monthly"]),
                annual_projected=quantize_inr(v["annual"]),
                actual_spent=quantize_inr(v["actual"]),
                count=v["count"],
            )
            for k, v in sorted(prov_agg.items(), key=lambda kv: kv[1]["monthly"], reverse=True)
        ]
        trend = []
        for ym in sorted(monthly_trend_map.keys())[-12:]:
            dt_m = dt.datetime.strptime(ym, "%Y-%m").date()
            trend.append(
                MonthlySpendPoint(
                    month=ym,
                    label=dt_m.strftime("%b %Y"),
                    actual_spent=quantize_inr(monthly_trend_map[ym]["actual"]),
                    payment_count=monthly_trend_map[ym]["count"],
                )
            )

        most_expensive = sorted(
            [s for s in active if s.monthly_equivalent is not None],
            key=lambda s: s.monthly_equivalent or Decimal("0.00"),
            reverse=True,
        )[:5]
        upcoming = sorted(
            [s for s in subs if s.status in {"active", "trial"} and s.next_renewal_date],
            key=lambda s: s.next_renewal_date or dt.date.max,
        )[:10]
        price_changes.sort(key=lambda h: h.effective_date, reverse=True)

        return SubscriptionAnalyticsResponse(
            monthly_recurring_cost=monthly_cost,
            annual_recurring_cost=annual_cost,
            total_actual_historical_spend=quantize_inr(total_actual),
            active_subscriptions_count=len(active),
            cancelled_subscriptions_count=len(cancelled),
            price_increase_events_count=price_increase_count,
            by_category=by_cat,
            by_provider=by_prov,
            monthly_trend=trend,
            most_expensive=most_expensive,
            upcoming_commitments=upcoming,
            recent_price_changes=price_changes[:15],
        )

    def list_candidates(self, db: Session, user: User) -> list[SubscriptionCandidateResponse]:
        expense_txs = list(
            db.execute(
                select(FinancialTransaction)
                .join(FinancialAccount, FinancialTransaction.account_id == FinancialAccount.id)
                .where(
                    FinancialTransaction.user_id == user.id,
                    FinancialTransaction.transaction_type == "expense",
                    FinancialTransaction.transfer_id.is_(None),
                    FinancialAccount.status != "disconnected",
                )
                .order_by(FinancialTransaction.transaction_date.asc())
            )
            .scalars()
            .all()
        )
        existing_subs = self.sub_repo.list_by_user(db, user.id, include_archived=True)
        linked_tx_ids = self.sub_repo.list_linked_tx_ids(db, user.id)
        decisions = self.sub_repo.list_candidate_decisions(db, user.id)
        return detect_subscription_candidates(expense_txs, existing_subs, linked_tx_ids, decisions)

    def handle_candidate_decision(
        self, db: Session, user: User, req: SubscriptionCandidateActionRequest
    ) -> dict[str, str]:
        if req.action == "link":
            if not req.subscription_id:
                raise HTTPException(
                    status_code=400, detail="subscription_id is required when linking a candidate."
                )
            sub = self.sub_repo.get_by_id(db, req.subscription_id, user.id)
            if not sub:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found."
                )
        self.sub_repo.upsert_candidate_decision(
            db,
            user.id,
            req.merchant_key.strip()[:150],
            "ignored" if req.action == "ignore" else "linked",
            linked_subscription_id=req.subscription_id,
        )
        db.commit()
        return {"status": "ok", "action": req.action}
