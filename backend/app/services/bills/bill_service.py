import datetime as dt
import math
import uuid
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.bills import (
    Bill,
    BillDocument,
    BillPayment,
    BillRecurrenceSchedule,
    Notification,
)
from app.models.finance import FinancialTransaction, FinancialTransfer
from app.models.user import User
from app.repositories.bills.bill_repository import BillRepository
from app.repositories.finance.account_repository import AccountRepository
from app.repositories.finance.category_repository import CategoryRepository
from app.repositories.finance.transaction_repository import TransactionRepository
from app.repositories.finance.transfer_repository import TransferRepository
from app.schemas.bills import (
    BillCreateRequest,
    BillDocumentResponse,
    BillListResponse,
    BillPaymentCreateRequest,
    BillPaymentLinkTransactionRequest,
    BillPaymentListResponse,
    BillPaymentResponse,
    BillReminderResponse,
    BillReminderUpdateRequest,
    BillResponse,
    BillsOverviewResponse,
    BillUpdateRequest,
    GenerateOccurrenceResponse,
    NotificationListResponse,
    NotificationResponse,
    RecurrenceScheduleResponse,
    RecurrenceScheduleUpdateRequest,
)
from app.schemas.finance.transaction import TransactionCreateRequest
from app.services.bills.bill_storage import BillDocumentStorage, validate_bill_document
from app.services.bills.recurrence import advance_due_date, compute_billing_period_for_due
from app.services.bills.reminder_service import ReminderService
from app.services.bills.status_engine import (
    compute_bill_derived_status,
    compute_remaining_due,
    get_effective_target_amount,
    resolve_user_today,
)
from app.services.finance.category_service import CategoryService
from app.services.finance.ledger_service import LedgerService
from app.services.finance.transaction_service import TransactionService

BILL_TO_SYSTEM_CATEGORY: dict[str, str] = {
    "electricity": "Utilities & Bills",
    "water": "Utilities & Bills",
    "gas": "Utilities & Bills",
    "internet": "Utilities & Bills",
    "mobile_postpaid": "Utilities & Bills",
    "mobile_recharge": "Utilities & Bills",
    "rent": "Housing & Rent",
    "maintenance": "Housing & Rent",
    "insurance": "Insurance",
    "loan_emi": "Other Expenses",
    "credit_card": "Other Expenses",
    "other": "Other Expenses",
}


class BillService:
    """
    Core service orchestrating bills CRUD, deterministic due-date status evaluation,
    controlled recurring occurrence generation, atomic Transaction/Ledger payment integration,
    private document uploads, and persistent user notifications.
    """

    def __init__(self, doc_storage: BillDocumentStorage | None = None):
        self.bill_repo = BillRepository()
        self.account_repo = AccountRepository()
        self.category_repo = CategoryRepository()
        self.category_service = CategoryService()
        self.transaction_repo = TransactionRepository()
        self.transfer_repo = TransferRepository()
        self.transaction_service = TransactionService()
        self.ledger_service = LedgerService()
        self.reminder_service = ReminderService()
        self.doc_storage = doc_storage or BillDocumentStorage()

    def _user_tz(self, user: User) -> str:
        return (
            user.preferences.timezone
            if user.preferences and user.preferences.timezone
            else "Asia/Kolkata"
        )

    def _resolve_category_id(
        self, db: Session, user: User, bill_category: str, explicit_category_id: uuid.UUID | None
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
        sys_name = BILL_TO_SYSTEM_CATEGORY.get(bill_category, "Other Expenses")
        cat = self.category_repo.get_system_category_by_name(db, sys_name, "expense")
        return cat.id if cat else None

    def _validate_optional_account(
        self, db: Session, user: User, account_id: uuid.UUID | None
    ):
        if account_id is None:
            return None
        acc = self.account_repo.get_by_id(db, account_id, user.id)
        if not acc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Linked financial account not found.",
            )
        if acc.status != "active":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Linked financial account is archived.",
            )
        return acc

    def _payment_to_response(self, p: BillPayment) -> BillPaymentResponse:
        return BillPaymentResponse(
            id=p.id,
            user_id=p.user_id,
            bill_id=p.bill_id,
            bill_name=p.bill.bill_name if p.bill else None,
            financial_account_id=p.financial_account_id,
            account_name=p.financial_account.name if p.financial_account else None,
            transaction_id=p.transaction_id,
            transfer_id=p.transfer_id,
            amount_paid=p.amount_paid,
            currency=p.currency,
            payment_date=p.payment_date,
            payment_method=p.payment_method,
            reference_number=p.reference_number,
            notes=p.notes,
            created_at=p.created_at,
        )

    def _bill_to_response(self, bill: Bill, user_today: dt.date) -> BillResponse:
        derived = compute_bill_derived_status(bill, today=user_today)
        remaining = compute_remaining_due(bill)
        target = get_effective_target_amount(bill)
        is_unknown = derived != "paid" and target is None
        days_until = (bill.due_date - user_today).days

        return BillResponse(
            id=bill.id,
            user_id=bill.user_id,
            parent_schedule_id=bill.parent_schedule_id,
            financial_category_id=bill.financial_category_id,
            financial_category_name=(
                bill.financial_category.name if bill.financial_category else None
            ),
            linked_account_id=bill.linked_account_id,
            linked_account_name=bill.linked_account.name if bill.linked_account else None,
            bill_name=bill.bill_name,
            bill_category=bill.bill_category,
            provider_name=bill.provider_name,
            account_reference=bill.account_reference,
            description=bill.description,
            bill_type=bill.bill_type,
            frequency=bill.frequency,
            is_variable_amount=bill.is_variable_amount,
            expected_amount=bill.expected_amount,
            current_amount=bill.current_amount,
            amount_paid_total=bill.amount_paid_total,
            remaining_due=remaining,
            is_amount_unknown=is_unknown,
            currency=bill.currency,
            billing_period_start=bill.billing_period_start,
            billing_period_end=bill.billing_period_end,
            due_date=bill.due_date,
            paid_at=bill.paid_at,
            stored_status=bill.stored_status,
            derived_status=derived,
            days_until_due=days_until,
            preferred_payment_method=bill.preferred_payment_method,
            reminder_enabled=bill.reminder_enabled,
            reminder_days_before=list(bill.reminder_days_before or []),
            notification_channels=dict(bill.notification_channels or {}),
            is_active=bill.is_active,
            created_at=bill.created_at,
            updated_at=bill.updated_at,
            payments=[self._payment_to_response(p) for p in (bill.payments or [])],
            reminders=[BillReminderResponse.model_validate(r) for r in (bill.reminders or [])],
            documents=[BillDocumentResponse.model_validate(d) for d in (bill.documents or [])],
            schedule=(
                RecurrenceScheduleResponse.model_validate(bill.schedule)
                if bill.schedule
                else None
            ),
        )

    def create_bill(self, db: Session, user: User, req: BillCreateRequest) -> BillResponse:
        tz = self._user_tz(user)
        user_today = resolve_user_today(tz)
        cat_id = self._resolve_category_id(db, user, req.bill_category, req.financial_category_id)
        self._validate_optional_account(db, user, req.linked_account_id)

        current_amt = req.current_amount
        expected_amt = req.expected_amount
        if not req.is_variable_amount:
            if current_amt is None:
                current_amt = expected_amt
            if expected_amt is None:
                expected_amt = current_amt

        channels_dict = req.notification_channels.model_dump()

        try:
            schedule: BillRecurrenceSchedule | None = None
            if req.bill_type == "recurring":
                assert req.frequency is not None
                next_due = advance_due_date(
                    req.due_date,
                    req.frequency,
                    anchor_day=req.due_date.day,
                    custom_interval_days=req.custom_interval_days,
                )
                schedule = BillRecurrenceSchedule(
                    user_id=user.id,
                    bill_name=req.bill_name.strip(),
                    bill_category=req.bill_category,
                    provider_name=req.provider_name.strip() if req.provider_name else None,
                    account_reference=(
                        req.account_reference.strip() if req.account_reference else None
                    ),
                    description=req.description.strip() if req.description else None,
                    financial_category_id=cat_id,
                    linked_account_id=req.linked_account_id,
                    preferred_payment_method=req.preferred_payment_method,
                    frequency=req.frequency,
                    custom_interval_days=req.custom_interval_days,
                    anchor_day=req.due_date.day,
                    is_variable_amount=req.is_variable_amount,
                    expected_amount=expected_amt,
                    currency=req.currency.upper(),
                    start_date=req.due_date,
                    end_date=req.end_date,
                    next_due_date=next_due,
                    is_active=True,
                    reminder_enabled=req.reminder_enabled,
                    reminder_days_before=req.reminder_days_before,
                    notification_channels=channels_dict,
                )
                self.bill_repo.create_schedule(db, schedule)

            p_start, p_end = (req.billing_period_start, req.billing_period_end)
            if p_start is None and req.bill_type == "recurring":
                p_start, p_end = compute_billing_period_for_due(req.due_date, req.frequency)

            bill = Bill(
                user_id=user.id,
                parent_schedule_id=schedule.id if schedule else None,
                financial_category_id=cat_id,
                linked_account_id=req.linked_account_id,
                bill_name=req.bill_name.strip(),
                bill_category=req.bill_category,
                provider_name=req.provider_name.strip() if req.provider_name else None,
                account_reference=req.account_reference.strip() if req.account_reference else None,
                description=req.description.strip() if req.description else None,
                bill_type=req.bill_type,
                frequency=req.frequency,
                is_variable_amount=req.is_variable_amount,
                expected_amount=expected_amt,
                current_amount=current_amt,
                currency=req.currency.upper(),
                billing_period_start=p_start,
                billing_period_end=p_end,
                due_date=req.due_date,
                stored_status="unpaid",
                preferred_payment_method=req.preferred_payment_method,
                reminder_enabled=req.reminder_enabled,
                reminder_days_before=req.reminder_days_before,
                notification_channels=channels_dict,
                is_active=True,
            )
            self.bill_repo.create_bill(db, bill)
            self.reminder_service.sync_reminders_for_bill(db, bill, user_timezone=tz)

            db.commit()
            loaded = self.bill_repo.get_bill(db, bill.id, user.id)
            assert loaded is not None
            return self._bill_to_response(loaded, user_today)
        except Exception:
            db.rollback()
            raise

    def list_bills(
        self,
        db: Session,
        user: User,
        status_filter: str | None = None,
        bill_category: str | None = None,
        bill_type: str | None = None,
        start_date: dt.date | None = None,
        end_date: dt.date | None = None,
        search: str | None = None,
        sort_by: str = "due_date_asc",
        include_archived: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> BillListResponse:
        user_today = resolve_user_today(self._user_tz(user))
        raw_bills = self.bill_repo.list_bills_by_user(
            db=db,
            user_id=user.id,
            include_archived=include_archived or status_filter == "archived",
            bill_category=bill_category,
            bill_type=bill_type,
            start_date=start_date,
            end_date=end_date,
            search=search,
        )

        responses = [self._bill_to_response(b, user_today) for b in raw_bills]

        if status_filter == "active":
            responses = [
                b
                for b in responses
                if b.derived_status in {"upcoming", "due_soon", "overdue", "partially_paid"}
            ]
        elif status_filter:
            responses = [b for b in responses if b.derived_status == status_filter]

        if sort_by == "due_date_desc":
            responses.sort(key=lambda b: b.due_date, reverse=True)
        elif sort_by == "amount_desc":
            responses.sort(
                key=lambda b: b.remaining_due if b.remaining_due is not None else (b.current_amount or Decimal("0.00")),
                reverse=True,
            )
        elif sort_by == "amount_asc":
            responses.sort(
                key=lambda b: b.remaining_due if b.remaining_due is not None else (b.current_amount or Decimal("0.00")),
            )
        elif sort_by == "name_asc":
            responses.sort(key=lambda b: b.bill_name.lower())
        else:  # due_date_asc
            responses.sort(key=lambda b: b.due_date)

        total = len(responses)
        total_pages = math.ceil(total / page_size) if total > 0 else 1
        offset = max(0, (page - 1) * page_size)
        paged = responses[offset : offset + page_size]

        return BillListResponse(
            items=paged,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    def get_bills_overview(self, db: Session, user: User) -> BillsOverviewResponse:
        user_today = resolve_user_today(self._user_tz(user))
        raw_bills = self.bill_repo.list_bills_by_user(db=db, user_id=user.id, include_archived=False)
        bills = [self._bill_to_response(b, user_today) for b in raw_bills]

        upcoming_bills = [b for b in bills if b.derived_status in {"upcoming", "due_soon"}]
        due_soon_bills = [b for b in bills if b.derived_status == "due_soon"]
        overdue_bills = [b for b in bills if b.derived_status == "overdue"]
        paid_bills = [b for b in bills if b.derived_status == "paid"]

        upcoming_known = sum(
            (b.remaining_due for b in upcoming_bills if b.remaining_due is not None),
            Decimal("0.00"),
        )
        overdue_known = sum(
            (b.remaining_due for b in overdue_bills if b.remaining_due is not None),
            Decimal("0.00"),
        )
        total_paid = sum((b.amount_paid_total for b in bills), Decimal("0.00"))
        unknown_var_count = sum(1 for b in bills if b.is_amount_unknown)

        unpaid_sorted = sorted(
            [b for b in bills if b.derived_status in {"overdue", "due_soon", "upcoming"}],
            key=lambda b: b.due_date,
        )
        next_due = unpaid_sorted[0] if unpaid_sorted else None

        recent_payments = [
            self._payment_to_response(p)
            for p in self.bill_repo.list_payments(db, user.id, limit=8)
        ]
        _, _, unread_count = self.bill_repo.list_notifications(db, user.id, unread_only=False, limit=1)

        return BillsOverviewResponse(
            upcoming_count=len(upcoming_bills),
            due_soon_count=len(due_soon_bills),
            overdue_count=len(overdue_bills),
            paid_count=len(paid_bills),
            total_upcoming_known_amount=upcoming_known,
            total_overdue_known_amount=overdue_known,
            total_paid_amount=total_paid,
            unknown_variable_bills_count=unknown_var_count,
            next_payment_due=next_due,
            recent_payments=recent_payments,
            unread_notifications_count=unread_count,
            due_soon_threshold_days=settings.BILL_DUE_SOON_DAYS,
        )

    def get_bill(self, db: Session, user: User, bill_id: uuid.UUID) -> BillResponse:
        bill = self.bill_repo.get_bill(db, bill_id, user.id)
        if not bill:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found.")
        return self._bill_to_response(bill, resolve_user_today(self._user_tz(user)))

    def update_bill(
        self, db: Session, user: User, bill_id: uuid.UUID, req: BillUpdateRequest
    ) -> BillResponse:
        bill = self.bill_repo.get_bill(db, bill_id, user.id)
        if not bill:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found.")
        if bill.stored_status == "archived":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Archived bills cannot be edited.",
            )

        if req.bill_name is not None:
            stripped = req.bill_name.strip()
            if not stripped:
                raise HTTPException(status_code=400, detail="Bill name cannot be blank.")
            bill.bill_name = stripped
        if req.bill_category is not None:
            bill.bill_category = req.bill_category
        if req.provider_name is not None:
            bill.provider_name = req.provider_name.strip() or None
        if req.account_reference is not None:
            bill.account_reference = req.account_reference.strip() or None
        if req.description is not None:
            bill.description = req.description.strip() or None
        if req.is_variable_amount is not None:
            bill.is_variable_amount = req.is_variable_amount
        if req.expected_amount is not None:
            bill.expected_amount = req.expected_amount
            if bill.parent_schedule_id and bill.stored_status != "paid":
                sched = self.bill_repo.get_schedule(db, bill.parent_schedule_id, user.id)
                if sched and sched.is_active:
                    sched.expected_amount = req.expected_amount
                    db.add(sched)
        if req.current_amount is not None:
            bill.current_amount = req.current_amount
        if req.due_date is not None:
            bill.due_date = req.due_date
        if req.preferred_payment_method is not None:
            bill.preferred_payment_method = req.preferred_payment_method
        if req.financial_category_id is not None:
            bill.financial_category_id = self._resolve_category_id(
                db, user, bill.bill_category, req.financial_category_id
            )
        if req.linked_account_id is not None:
            self._validate_optional_account(db, user, req.linked_account_id)
            bill.linked_account_id = req.linked_account_id
        if req.reminder_enabled is not None:
            bill.reminder_enabled = req.reminder_enabled
        if req.reminder_days_before is not None:
            bill.reminder_days_before = sorted(
                {d for d in req.reminder_days_before if 0 <= d <= 60}, reverse=True
            ) or [7, 3, 1, 0]
        if req.notification_channels is not None:
            bill.notification_channels = req.notification_channels.model_dump()

        # Re-evaluate stored_status cleanly if amount changed on an unpaid/partial bill
        if bill.stored_status != "paid":
            target = get_effective_target_amount(bill)
            if target is not None and bill.amount_paid_total >= target:
                bill.stored_status = "paid"
                bill.paid_at = bill.paid_at or dt.datetime.now(dt.UTC)

        db.add(bill)
        db.flush()
        self.reminder_service.sync_reminders_for_bill(db, bill, user_timezone=self._user_tz(user))
        db.commit()

        loaded = self.bill_repo.get_bill(db, bill.id, user.id)
        assert loaded is not None
        return self._bill_to_response(loaded, resolve_user_today(self._user_tz(user)))

    def archive_bill(self, db: Session, user: User, bill_id: uuid.UUID) -> BillResponse:
        bill = self.bill_repo.get_bill(db, bill_id, user.id)
        if not bill:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found.")

        bill.is_active = False
        bill.stored_status = "archived"
        db.add(bill)
        self.reminder_service.sync_reminders_for_bill(db, bill, user_timezone=self._user_tz(user))
        db.commit()

        loaded = self.bill_repo.get_bill(db, bill.id, user.id)
        assert loaded is not None
        return self._bill_to_response(loaded, resolve_user_today(self._user_tz(user)))

    def _spawn_next_occurrence_if_applicable(
        self, db: Session, user: User, schedule: BillRecurrenceSchedule
    ) -> Bill | None:
        """
        Idempotently creates the next unpaid recurring occurrence if schedule is active
        and next_due_date does not exceed schedule.end_date.
        Never marks it paid or creates a payment transaction.
        """
        if not schedule.is_active:
            return None
        if schedule.end_date is not None and schedule.next_due_date > schedule.end_date:
            return None

        due = schedule.next_due_date
        existing = self.bill_repo.get_occurrence_by_schedule_and_due(db, schedule.id, due)
        if existing:
            return existing

        p_start, p_end = compute_billing_period_for_due(due, schedule.frequency)
        occ = Bill(
            user_id=user.id,
            parent_schedule_id=schedule.id,
            financial_category_id=schedule.financial_category_id,
            linked_account_id=schedule.linked_account_id,
            bill_name=schedule.bill_name,
            bill_category=schedule.bill_category,
            provider_name=schedule.provider_name,
            account_reference=schedule.account_reference,
            description=schedule.description,
            bill_type="recurring",
            frequency=schedule.frequency,
            is_variable_amount=schedule.is_variable_amount,
            expected_amount=schedule.expected_amount,
            current_amount=None if schedule.is_variable_amount else schedule.expected_amount,
            currency=schedule.currency,
            billing_period_start=p_start,
            billing_period_end=p_end,
            due_date=due,
            stored_status="unpaid",
            preferred_payment_method=schedule.preferred_payment_method,
            reminder_enabled=schedule.reminder_enabled,
            reminder_days_before=list(schedule.reminder_days_before or [7, 3, 1, 0]),
            notification_channels=dict(
                schedule.notification_channels or {"in_app": True, "email": False, "sms": False}
            ),
            is_active=True,
        )
        self.bill_repo.create_bill(db, occ)
        self.reminder_service.sync_reminders_for_bill(db, occ, user_timezone=self._user_tz(user))

        schedule.next_due_date = advance_due_date(
            due,
            schedule.frequency,
            anchor_day=schedule.anchor_day,
            custom_interval_days=schedule.custom_interval_days,
        )
        db.add(schedule)
        db.flush()
        return occ

    def record_payment(
        self,
        db: Session,
        user: User,
        bill_id: uuid.UUID,
        req: BillPaymentCreateRequest,
    ) -> BillResponse:
        """
        Atomically records a bill payment by:
        1. Locking the bill row (FOR UPDATE) and verifying ownership & idempotency.
        2. Validating owned active financial account & preventing negative asset balances.
        3. Creating the authoritative FinancialTransaction + LedgerJournal via TransactionService
           (or Credit Card settlement transfer when paying a linked credit_card account without double counting).
        4. Updating Bill amount_paid_total, stored_status, cancelling stale reminders, creating paid notification,
           and spawning next recurring occurrence when settled.
        """
        if req.idempotency_key:
            dup = self.bill_repo.get_payment_by_idempotency(
                db, user.id, bill_id, req.idempotency_key
            )
            if dup:
                return self.get_bill(db, user, bill_id)

        bill = self.bill_repo.get_bill_for_update(db, bill_id, user.id)
        if not bill:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found.")
        if not bill.is_active or bill.stored_status == "archived":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot record payments on an archived bill.",
            )
        if bill.stored_status == "paid":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This bill has already been marked as fully paid.",
            )

        account = self.account_repo.get_by_id(db, req.financial_account_id, user.id)
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment financial account not found.",
            )
        if account.status != "active":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot pay from an archived account.",
            )
        if account.account_type != "credit_card" and req.amount_paid > account.current_balance:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Insufficient balance in '{account.name}'. Available balance is "
                    f"₹{account.current_balance:,.2f}, cannot record payment of ₹{req.amount_paid:,.2f}."
                ),
            )

        try:
            tx_id: uuid.UUID | None = None
            tr_id: uuid.UUID | None = None

            # Credit card bill settled from an asset account uses transfer accounting (no duplicate expense!)
            linked_acc = (
                self.account_repo.get_by_id(db, bill.linked_account_id, user.id)
                if bill.linked_account_id
                else None
            )
            if (
                bill.bill_category == "credit_card"
                and linked_acc is not None
                and linked_acc.account_type == "credit_card"
                and linked_acc.status == "active"
                and linked_acc.id != account.id
            ):
                transfer = FinancialTransfer(
                    user_id=user.id,
                    source_account_id=account.id,
                    destination_account_id=linked_acc.id,
                    amount=req.amount_paid,
                    currency=account.currency,
                    transfer_date=req.payment_date,
                    description=f"Bill payment: {bill.bill_name}",
                    status="completed",
                )
                self.transfer_repo.create(db, transfer)

                src_tx = FinancialTransaction(
                    user_id=user.id,
                    account_id=account.id,
                    transaction_type="transfer",
                    amount=req.amount_paid,
                    currency=account.currency,
                    description=f"Card bill payment to {linked_acc.name}: {bill.bill_name}",
                    transaction_date=req.payment_date,
                    source="bill_payment",
                    transfer_id=transfer.id,
                )
                dst_tx = FinancialTransaction(
                    user_id=user.id,
                    account_id=linked_acc.id,
                    transaction_type="transfer",
                    amount=req.amount_paid,
                    currency=linked_acc.currency,
                    description=f"Card bill payment from {account.name}: {bill.bill_name}",
                    transaction_date=req.payment_date,
                    source="bill_payment",
                    transfer_id=transfer.id,
                )
                self.transaction_repo.create(db, src_tx)
                self.transaction_repo.create(db, dst_tx)
                transfer.source_transaction_id = src_tx.id
                transfer.destination_transaction_id = dst_tx.id
                self.transfer_repo.update(db, transfer)

                self.ledger_service.post_transfer(
                    db=db,
                    user_id=user.id,
                    transfer_id=transfer.id,
                    source_account_id=account.id,
                    source_account_type=account.account_type,
                    dest_account_id=linked_acc.id,
                    dest_account_type=linked_acc.account_type,
                    amount=req.amount_paid,
                    entry_date=req.payment_date,
                    description=f"Bill payment: {bill.bill_name}",
                    currency=account.currency,
                )
                tr_id = transfer.id
                tx_id = src_tx.id
            else:
                tx_req = TransactionCreateRequest(
                    account_id=account.id,
                    transaction_type="expense",
                    amount=req.amount_paid,
                    currency=bill.currency,
                    category_id=bill.financial_category_id,
                    description=f"Bill Payment: {bill.bill_name}",
                    merchant_payee=bill.provider_name,
                    transaction_date=req.payment_date,
                    notes=req.notes or f"Paid via {req.payment_method.upper()}",
                )
                created_tx = self.transaction_service.create_transaction(
                    db=db,
                    user=user,
                    req=tx_req,
                    source="bill_payment",
                    commit=False,
                )
                tx_id = created_tx.id

            # Double-check asset balance non-negative post-ledger flush
            db.refresh(account)
            if account.account_type != "credit_card" and account.current_balance < Decimal("0.00"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Payment would make '{account.name}' balance negative.",
                )

            payment = BillPayment(
                user_id=user.id,
                bill_id=bill.id,
                financial_account_id=account.id,
                transaction_id=tx_id,
                transfer_id=tr_id,
                amount_paid=req.amount_paid,
                currency=bill.currency,
                payment_date=req.payment_date,
                payment_method=req.payment_method,
                reference_number=req.reference_number.strip() if req.reference_number else None,
                notes=req.notes.strip() if req.notes else None,
                idempotency_key=req.idempotency_key,
            )
            self.bill_repo.create_payment(db, payment)

            bill.amount_paid_total = Decimal(bill.amount_paid_total or Decimal("0.00")) + req.amount_paid
            if bill.current_amount is None and req.mark_as_fully_paid:
                bill.current_amount = bill.amount_paid_total

            target = get_effective_target_amount(bill)
            settled = req.mark_as_fully_paid or (
                target is not None and bill.amount_paid_total >= target
            )
            now_utc = dt.datetime.now(dt.UTC)
            if settled:
                bill.stored_status = "paid"
                bill.paid_at = now_utc
            else:
                bill.stored_status = "partially_paid"

            db.add(bill)
            self.reminder_service.sync_reminders_for_bill(
                db, bill, user_timezone=self._user_tz(user)
            )

            # Create payment confirmation in-app notification
            self.bill_repo.create_notification(
                db,
                Notification(
                    user_id=user.id,
                    title=f"Payment Recorded: {bill.bill_name}",
                    message=(
                        f"Recorded payment of ₹{req.amount_paid:,.2f} for {bill.bill_name} "
                        f"on {req.payment_date.strftime('%d/%m/%Y')} via {req.payment_method.upper()}."
                    ),
                    notification_type="bill_paid",
                    related_bill_id=bill.id,
                    related_payment_id=payment.id,
                    dedupe_key=f"paid:{payment.id}",
                ),
            )

            # Spawn next recurring occurrence only if settled & active schedule
            if settled and bill.parent_schedule_id:
                sched = self.bill_repo.get_schedule(db, bill.parent_schedule_id, user.id)
                if sched and sched.is_active:
                    self._spawn_next_occurrence_if_applicable(db, user, sched)

            db.commit()
            return self.get_bill(db, user, bill.id)
        except Exception:
            db.rollback()
            raise

    def link_existing_transaction(
        self,
        db: Session,
        user: User,
        bill_id: uuid.UUID,
        req: BillPaymentLinkTransactionRequest,
    ) -> BillResponse:
        """
        Safely links an already-recorded transaction (e.g. from Phase 3 CSV import or Phase 2 manual entry)
        to a bill without creating a duplicate financial expense or ledger entry.
        """
        bill = self.bill_repo.get_bill_for_update(db, bill_id, user.id)
        if not bill:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found.")
        if not bill.is_active or bill.stored_status == "archived":
            raise HTTPException(status_code=400, detail="Archived bills cannot accept payments.")
        if bill.stored_status == "paid":
            raise HTTPException(status_code=400, detail="Bill is already marked paid.")

        tx = self.transaction_repo.get_by_id(db, req.transaction_id, user.id)
        if not tx:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Financial transaction not found.",
            )
        if tx.transaction_type not in {"expense", "transfer"}:
            raise HTTPException(
                status_code=400,
                detail="Only expense or transfer payment transactions can settle a bill.",
            )
        existing_link = self.bill_repo.get_payment_by_transaction(db, tx.id)
        if existing_link:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This financial transaction is already linked to a bill payment.",
            )

        try:
            payment = BillPayment(
                user_id=user.id,
                bill_id=bill.id,
                financial_account_id=tx.account_id,
                transaction_id=tx.id,
                transfer_id=tx.transfer_id,
                amount_paid=tx.amount,
                currency=tx.currency,
                payment_date=tx.transaction_date,
                payment_method=req.payment_method,
                reference_number=tx.external_reference,
                notes=req.notes or f"Linked existing transaction: {tx.description}",
            )
            self.bill_repo.create_payment(db, payment)

            bill.amount_paid_total = Decimal(bill.amount_paid_total or Decimal("0.00")) + tx.amount
            if bill.current_amount is None and req.mark_as_fully_paid:
                bill.current_amount = bill.amount_paid_total
            target = get_effective_target_amount(bill)
            settled = req.mark_as_fully_paid or (
                target is not None and bill.amount_paid_total >= target
            )
            if settled:
                bill.stored_status = "paid"
                bill.paid_at = dt.datetime.now(dt.UTC)
            else:
                bill.stored_status = "partially_paid"

            db.add(bill)
            self.reminder_service.sync_reminders_for_bill(
                db, bill, user_timezone=self._user_tz(user)
            )
            if settled and bill.parent_schedule_id:
                sched = self.bill_repo.get_schedule(db, bill.parent_schedule_id, user.id)
                if sched and sched.is_active:
                    self._spawn_next_occurrence_if_applicable(db, user, sched)

            db.commit()
            return self.get_bill(db, user, bill.id)
        except Exception:
            db.rollback()
            raise

    def list_payment_history(
        self, db: Session, user: User, bill_id: uuid.UUID | None = None
    ) -> BillPaymentListResponse:
        if bill_id is not None:
            bill = self.bill_repo.get_bill(db, bill_id, user.id)
            if not bill:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found.")
        rows = self.bill_repo.list_payments(db, user.id, bill_id=bill_id)
        return BillPaymentListResponse(
            items=[self._payment_to_response(p) for p in rows],
            total=len(rows),
        )

    def list_schedules(self, db: Session, user: User) -> list[RecurrenceScheduleResponse]:
        return [
            RecurrenceScheduleResponse.model_validate(s)
            for s in self.bill_repo.list_schedules(db, user.id)
        ]

    def update_schedule(
        self,
        db: Session,
        user: User,
        schedule_id: uuid.UUID,
        req: RecurrenceScheduleUpdateRequest,
    ) -> RecurrenceScheduleResponse:
        sched = self.bill_repo.get_schedule(db, schedule_id, user.id)
        if not sched:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Recurring schedule not found.",
            )
        if req.frequency is not None:
            if req.frequency == "custom" and not (
                req.custom_interval_days or sched.custom_interval_days
            ):
                raise HTTPException(
                    status_code=400, detail="custom_interval_days is required for custom frequency."
                )
            sched.frequency = req.frequency
        if req.custom_interval_days is not None:
            sched.custom_interval_days = req.custom_interval_days
        if req.expected_amount is not None:
            sched.expected_amount = req.expected_amount
        if req.is_variable_amount is not None:
            sched.is_variable_amount = req.is_variable_amount
        if req.clear_end_date:
            sched.end_date = None
        elif req.end_date is not None:
            sched.end_date = req.end_date
        if req.is_active is not None:
            sched.is_active = req.is_active

        db.add(sched)
        db.commit()
        db.refresh(sched)
        return RecurrenceScheduleResponse.model_validate(sched)

    def generate_next_occurrence_for_schedule(
        self, db: Session, user: User, schedule_id: uuid.UUID
    ) -> GenerateOccurrenceResponse:
        sched = self.bill_repo.get_schedule(db, schedule_id, user.id)
        if not sched:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Recurring schedule not found.",
            )
        if not sched.is_active:
            return GenerateOccurrenceResponse(
                created=False, message="Schedule is inactive; no new occurrence created."
            )
        if sched.end_date is not None and sched.next_due_date > sched.end_date:
            return GenerateOccurrenceResponse(
                created=False, message="Schedule has reached its end date."
            )

        existing = self.bill_repo.get_occurrence_by_schedule_and_due(
            db, sched.id, sched.next_due_date
        )
        if existing:
            return GenerateOccurrenceResponse(
                created=False,
                message="Occurrence for next_due_date already exists.",
                occurrence=self.get_bill(db, user, existing.id),
            )

        occ = self._spawn_next_occurrence_if_applicable(db, user, sched)
        db.commit()
        if not occ:
            return GenerateOccurrenceResponse(created=False, message="No occurrence created.")
        return GenerateOccurrenceResponse(
            created=True,
            message="Next recurring bill occurrence generated.",
            occurrence=self.get_bill(db, user, occ.id),
        )

    def update_bill_reminders(
        self, db: Session, user: User, bill_id: uuid.UUID, req: BillReminderUpdateRequest
    ) -> BillResponse:
        bill = self.bill_repo.get_bill(db, bill_id, user.id)
        if not bill:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found.")

        if req.reminder_enabled is not None:
            bill.reminder_enabled = req.reminder_enabled
        if req.reminder_days_before is not None:
            bill.reminder_days_before = sorted(
                {d for d in req.reminder_days_before if 0 <= d <= 60}, reverse=True
            ) or [7, 3, 1, 0]
        if req.notification_channels is not None:
            bill.notification_channels = req.notification_channels.model_dump()

        db.add(bill)
        self.reminder_service.sync_reminders_for_bill(db, bill, user_timezone=self._user_tz(user))
        db.commit()
        return self.get_bill(db, user, bill.id)

    def upload_document(
        self,
        db: Session,
        user: User,
        bill_id: uuid.UUID,
        filename: str | None,
        file_bytes: bytes,
    ) -> BillDocumentResponse:
        bill = self.bill_repo.get_bill(db, bill_id, user.id)
        if not bill:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found.")

        try:
            safe_name, ext, ctype, fhash = validate_bill_document(filename, file_bytes)
        except ValueError as err:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err

        storage_key: str | None = None
        try:
            storage_key = self.doc_storage.save(user.id, bill.id, ext, file_bytes)
            doc = BillDocument(
                user_id=user.id,
                bill_id=bill.id,
                original_filename=safe_name,
                file_type=ext,
                content_type=ctype,
                file_size=len(file_bytes),
                file_hash=fhash,
                storage_key=storage_key,
            )
            self.bill_repo.create_document(db, doc)
            db.commit()
            db.refresh(doc)
            return BillDocumentResponse.model_validate(doc)
        except Exception:
            db.rollback()
            if storage_key:
                self.doc_storage.delete(storage_key)
            raise

    def download_document(
        self, db: Session, user: User, bill_id: uuid.UUID, doc_id: uuid.UUID
    ) -> tuple[BillDocument, bytes]:
        doc = self.bill_repo.get_document(db, doc_id, bill_id, user.id)
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Bill document not found."
            )
        try:
            data = self.doc_storage.read_bytes(doc.storage_key)
            return doc, data
        except FileNotFoundError as err:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Stored document file not found on server.",
            ) from err

    def list_notifications(
        self, db: Session, user: User, unread_only: bool = False
    ) -> NotificationListResponse:
        items, total, unread = self.bill_repo.list_notifications(
            db, user.id, unread_only=unread_only
        )
        return NotificationListResponse(
            items=[NotificationResponse.model_validate(n) for n in items],
            total=total,
            unread_count=unread,
        )

    def mark_notification_read(
        self, db: Session, user: User, notification_id: uuid.UUID
    ) -> NotificationResponse:
        notif = self.bill_repo.get_notification(db, notification_id, user.id)
        if not notif:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found."
            )
        if not notif.is_read:
            notif.is_read = True
            notif.read_at = dt.datetime.now(dt.UTC)
            db.add(notif)
            db.commit()
            db.refresh(notif)
        return NotificationResponse.model_validate(notif)

    def mark_all_notifications_read(self, db: Session, user: User) -> dict[str, int]:
        updated = self.bill_repo.mark_all_notifications_read(db, user.id)
        db.commit()
        return {"marked_read": updated}
