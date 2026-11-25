import datetime as dt
import math
import uuid
from collections import defaultdict
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.bills import Notification
from app.models.finance import FinancialTransaction, FinancialTransfer
from app.models.loans import (
    Loan,
    LoanInstallment,
    LoanInterestRateHistory,
    LoanPayment,
)
from app.models.user import User
from app.repositories.bills.bill_repository import BillRepository
from app.repositories.finance.account_repository import AccountRepository
from app.repositories.finance.category_repository import CategoryRepository
from app.repositories.finance.ledger_repository import LedgerRepository
from app.repositories.finance.transaction_repository import TransactionRepository
from app.repositories.finance.transfer_repository import TransferRepository
from app.repositories.loans.loan_repository import LoanRepository
from app.schemas.bills import BillReminderResponse
from app.schemas.finance.account import AccountCreateRequest
from app.schemas.finance.transaction import TransactionCreateRequest
from app.schemas.loans import (
    EmiCalculatorRequest,
    EmiCalculatorResponse,
    EmiScheduleRowResponse,
    LoanAnalyticsResponse,
    LoanBreakdownItem,
    LoanCreateRequest,
    LoanInstallmentResponse,
    LoanInterestRateHistoryResponse,
    LoanInterestRateRevisionRequest,
    LoanListResponse,
    LoanOverviewResponse,
    LoanPaymentCreateRequest,
    LoanPaymentLinkRequest,
    LoanPaymentListResponse,
    LoanPaymentResponse,
    LoanPaymentReverseRequest,
    LoanPrepaymentScenarioRequest,
    LoanPrepaymentScenarioResponse,
    LoanResponse,
    LoanUpdateRequest,
)
from app.services.bills.reminder_service import ReminderService
from app.services.bills.status_engine import resolve_user_today
from app.services.finance.account_service import AccountService
from app.services.finance.category_service import CategoryService
from app.services.finance.ledger_service import LedgerService
from app.services.finance.transaction_service import TransactionService
from app.services.loans.emi_engine import (
    calculate_emi_summary,
    generate_amortization_schedule,
    q2,
    simulate_prepayment_scenario,
    solve_remaining_periods_for_emi,
)


class LoanService:
    """
    Service orchestrating loans, EMI calculator, amortization schedules,
    atomic principal (liability transfer) vs interest (expense) ledger accounting,
    floating rate revisions, prepayment simulations, reminders, and analytics.
    """

    def __init__(self):
        self.loan_repo = LoanRepository()
        self.bill_repo = BillRepository()
        self.account_repo = AccountRepository()
        self.category_repo = CategoryRepository()
        self.category_service = CategoryService()
        self.transaction_repo = TransactionRepository()
        self.transfer_repo = TransferRepository()
        self.ledger_repo = LedgerRepository()
        self.account_service = AccountService()
        self.transaction_service = TransactionService()
        self.ledger_service = LedgerService()
        self.reminder_service = ReminderService()

    def _user_tz(self, user: User) -> str:
        return (
            user.preferences.timezone
            if user.preferences and user.preferences.timezone
            else "Asia/Kolkata"
        )

    def _resolve_interest_category_id(self, db: Session) -> uuid.UUID | None:
        self.category_service.seed_default_categories(db, commit=False)
        cat = self.category_repo.get_system_category_by_name(db, "Loan Interest", "expense")
        if not cat:
            cat = self.category_repo.get_system_category_by_name(db, "Other Expenses", "expense")
        return cat.id if cat else None

    def _payment_to_response(self, p: LoanPayment) -> LoanPaymentResponse:
        return LoanPaymentResponse(
            id=p.id,
            user_id=p.user_id,
            loan_id=p.loan_id,
            loan_name=p.loan.loan_name if p.loan else None,
            installment_id=p.installment_id,
            payment_account_id=p.payment_account_id,
            account_name=p.payment_account.name if p.payment_account else None,
            principal_transfer_id=p.principal_transfer_id,
            interest_transaction_id=p.interest_transaction_id,
            fee_transaction_id=p.fee_transaction_id,
            linked_transaction_id=p.linked_transaction_id,
            payment_type=p.payment_type,
            payment_date=p.payment_date,
            principal_paid=p.principal_paid,
            interest_paid=p.interest_paid,
            fee_paid=p.fee_paid,
            total_paid=p.total_paid,
            reference_number=p.reference_number,
            payment_status=p.payment_status,
            reversal_reason=p.reversal_reason,
            notes=p.notes,
            created_at=p.created_at,
        )

    def _to_response(self, loan: Loan, user_today: dt.date) -> LoanResponse:
        active_installments = [
            inst for inst in (loan.installments or []) if inst.status != "cancelled"
        ]
        inst_responses: list[LoanInstallmentResponse] = []
        overdue_cnt = 0
        for inst in active_installments:
            derived = inst.status
            if inst.status in {"upcoming", "partially_paid"} and inst.due_date < user_today:
                derived = "overdue"
                overdue_cnt += 1
            elif inst.status == "upcoming" and 0 <= (inst.due_date - user_today).days <= 5:
                derived = "due_soon"
            r = LoanInstallmentResponse.model_validate(inst)
            r.derived_status = derived
            inst_responses.append(r)

        completed_payments = [p for p in (loan.payments or []) if p.payment_status == "completed"]
        total_prin = q2(sum((Decimal(p.principal_paid) for p in completed_payments), Decimal("0.00")))
        total_int = q2(sum((Decimal(p.interest_paid) for p in completed_payments), Decimal("0.00")))
        total_fee = q2(sum((Decimal(p.fee_paid) for p in completed_payments), Decimal("0.00")))

        denom = Decimal(loan.original_principal or loan.outstanding_principal_at_start)
        if denom > Decimal("0.00"):
            repaid_since_origin = max(Decimal("0.00"), denom - Decimal(loan.current_outstanding_principal))
            prog = min(Decimal("100.00"), q2((repaid_since_origin / denom) * Decimal("100")))
        else:
            prog = Decimal("100.00")

        derived_loan_status = loan.status
        if loan.status == "active" and overdue_cnt > 0:
            derived_loan_status = "overdue"

        return LoanResponse(
            id=loan.id,
            user_id=loan.user_id,
            liability_account_id=loan.liability_account_id,
            linked_repayment_account_id=loan.linked_repayment_account_id,
            linked_repayment_account_name=(
                loan.linked_repayment_account.name if loan.linked_repayment_account else None
            ),
            loan_name=loan.loan_name,
            lender_name=loan.lender_name,
            loan_type=loan.loan_type,
            original_principal=loan.original_principal,
            outstanding_principal_at_start=loan.outstanding_principal_at_start,
            current_outstanding_principal=loan.current_outstanding_principal,
            currency=loan.currency,
            interest_rate=loan.interest_rate,
            interest_rate_type=loan.interest_rate_type,
            calculation_method=loan.calculation_method,
            loan_start_date=loan.loan_start_date,
            tracking_start_date=loan.tracking_start_date,
            first_emi_date=loan.first_emi_date,
            next_emi_due_date=loan.next_emi_due_date,
            maturity_date=loan.maturity_date,
            original_tenure_months=loan.original_tenure_months,
            remaining_tenure_months=loan.remaining_tenure_months,
            emi_amount=loan.emi_amount,
            emi_frequency=loan.emi_frequency,
            anchor_day=loan.anchor_day,
            loan_reference=loan.loan_reference,
            processing_fee=loan.processing_fee,
            prepayment_charges_info=loan.prepayment_charges_info,
            notes=loan.notes,
            status=loan.status,
            derived_status=derived_loan_status,
            total_principal_repaid=total_prin,
            total_interest_paid=total_int,
            total_paid_overall=q2(total_prin + total_int + total_fee),
            repayment_progress_pct=prog,
            overdue_installments_count=overdue_cnt,
            reminder_enabled=loan.reminder_enabled,
            reminder_days_before=list(loan.reminder_days_before or []),
            notification_channels=dict(loan.notification_channels or {}),
            created_at=loan.created_at,
            updated_at=loan.updated_at,
            installments=inst_responses,
            rate_history=[
                LoanInterestRateHistoryResponse.model_validate(h)
                for h in (loan.rate_history or [])
            ],
            payments=[self._payment_to_response(p) for p in (loan.payments or [])],
            reminders=[BillReminderResponse.model_validate(r) for r in (loan.reminders or [])],
        )

    def calculate_emi_preview(self, req: EmiCalculatorRequest) -> EmiCalculatorResponse:
        emi, total_int, total_rep, assumptions = calculate_emi_summary(
            principal=req.principal,
            annual_interest_rate=req.annual_interest_rate,
            tenure_installments=req.tenure_installments,
            emi_frequency=req.emi_frequency,
            calculation_method=req.calculation_method,
        )
        today = resolve_user_today("Asia/Kolkata")
        proj = generate_amortization_schedule(
            opening_principal=req.principal,
            annual_interest_rate=req.annual_interest_rate,
            periods=req.tenure_installments,
            first_due_date=today,
            anchor_day=today.day,
            emi_amount=emi,
            emi_frequency=req.emi_frequency,
            calculation_method=req.calculation_method,
        )
        prin_pct = q2((req.principal / total_rep) * Decimal("100")) if total_rep > 0 else Decimal("100.00")
        int_pct = q2(Decimal("100.00") - prin_pct)
        return EmiCalculatorResponse(
            principal=q2(req.principal),
            annual_interest_rate=req.annual_interest_rate,
            tenure_installments=req.tenure_installments,
            emi_frequency=req.emi_frequency,
            calculation_method=req.calculation_method,
            periodic_emi=emi,
            total_repayment=total_rep,
            total_interest=total_int,
            principal_percentage=prin_pct,
            interest_percentage=int_pct,
            assumptions=assumptions,
            preview_schedule=[
                EmiScheduleRowResponse(
                    installment_number=r.installment_number,
                    due_date=r.due_date,
                    opening_principal=r.opening_principal,
                    emi_amount=r.emi_amount,
                    principal_component=r.principal_component,
                    interest_component=r.interest_component,
                    closing_principal=r.closing_principal,
                    is_final_adjustment=r.is_final_adjustment,
                )
                for r in proj
            ],
        )

    def _sync_installments_from_date(
        self,
        db: Session,
        loan: Loan,
        start_installment_number: int,
        first_due_date: dt.date,
        periods: int,
    ) -> None:
        proj = generate_amortization_schedule(
            opening_principal=loan.current_outstanding_principal,
            annual_interest_rate=loan.interest_rate,
            periods=periods,
            first_due_date=first_due_date,
            anchor_day=loan.anchor_day,
            emi_amount=loan.emi_amount,
            emi_frequency=loan.emi_frequency,
            calculation_method=loan.calculation_method,
            start_installment_number=start_installment_number,
        )
        for row in proj:
            self.loan_repo.add_installment(
                db,
                LoanInstallment(
                    user_id=loan.user_id,
                    loan_id=loan.id,
                    installment_number=row.installment_number,
                    due_date=row.due_date,
                    opening_principal=row.opening_principal,
                    emi_amount=row.emi_amount,
                    principal_component=row.principal_component,
                    interest_component=row.interest_component,
                    closing_principal=row.closing_principal,
                    status="upcoming",
                    is_final_adjustment=row.is_final_adjustment,
                ),
            )
        if proj:
            loan.next_emi_due_date = proj[0].due_date
            loan.maturity_date = proj[-1].due_date
            loan.remaining_tenure_months = len(proj)
        else:
            loan.next_emi_due_date = None
            loan.remaining_tenure_months = 0

    def create_loan(self, db: Session, user: User, req: LoanCreateRequest) -> LoanResponse:
        tz = self._user_tz(user)
        user_today = resolve_user_today(tz)

        if req.linked_repayment_account_id is not None:
            rep_acc = self.account_repo.get_by_id(db, req.linked_repayment_account_id, user.id)
            if not rep_acc or rep_acc.status != "active":
                raise HTTPException(
                    status_code=400, detail="Linked repayment account is invalid or archived."
                )

        disb_acc = None
        if req.record_disbursement_to_account_id is not None:
            disb_acc = self.account_repo.get_by_id(db, req.record_disbursement_to_account_id, user.id)
            if not disb_acc or disb_acc.status != "active" or disb_acc.account_type in {"credit_card", "loan_liability"}:
                raise HTTPException(
                    status_code=400,
                    detail="Disbursement destination must be an active bank/cash asset account.",
                )

        emi_amt = req.emi_amount
        if emi_amt is None:
            emi_amt, _, _, _ = calculate_emi_summary(
                principal=req.outstanding_principal,
                annual_interest_rate=req.interest_rate,
                tenure_installments=req.remaining_tenure_months,
                emi_frequency=req.emi_frequency,
                calculation_method=req.calculation_method,
            )

        try:
            # Create dedicated loan_liability FinancialAccount
            unique_acc_name = f"Loan: {req.loan_name.strip()} ({uuid.uuid4().hex[:4]})"
            opening_bal_for_acc = Decimal("0.00") if disb_acc else q2(req.outstanding_principal)
            liab_acc_resp = self.account_service.create_account(
                db=db,
                user=user,
                req=AccountCreateRequest(
                    name=unique_acc_name[:100],
                    account_type="loan_liability",
                    institution_name=req.lender_name.strip()[:100],
                    account_identifier=req.loan_reference[:50] if req.loan_reference else None,
                    currency="INR",
                    opening_balance=opening_bal_for_acc,
                ),
                source="loan",
                commit=False,
            )

            # If explicit disbursement to an asset account was requested:
            # Transfer FROM loan_liability TO bank account -> Credits loan_liability (+liability), Debits bank (+cash)
            if disb_acc is not None:
                tr = FinancialTransfer(
                    user_id=user.id,
                    source_account_id=liab_acc_resp.id,
                    destination_account_id=disb_acc.id,
                    amount=q2(req.outstanding_principal),
                    currency="INR",
                    transfer_date=req.loan_start_date,
                    description=f"Loan disbursement (borrowed funds): {req.loan_name.strip()}",
                    status="completed",
                )
                self.transfer_repo.create(db, tr)
                src_tx = FinancialTransaction(
                    user_id=user.id,
                    account_id=liab_acc_resp.id,
                    transaction_type="transfer",
                    amount=q2(req.outstanding_principal),
                    currency="INR",
                    description=f"Loan liability recognized: {req.loan_name.strip()}",
                    transaction_date=req.loan_start_date,
                    source="loan_payment",
                    transfer_id=tr.id,
                )
                dst_tx = FinancialTransaction(
                    user_id=user.id,
                    account_id=disb_acc.id,
                    transaction_type="transfer",
                    amount=q2(req.outstanding_principal),
                    currency="INR",
                    description=f"Loan disbursement received: {req.loan_name.strip()}",
                    transaction_date=req.loan_start_date,
                    source="loan_payment",
                    transfer_id=tr.id,
                )
                self.transaction_repo.create(db, src_tx)
                self.transaction_repo.create(db, dst_tx)
                tr.source_transaction_id = src_tx.id
                tr.destination_transaction_id = dst_tx.id
                self.transfer_repo.update(db, tr)

                self.ledger_service.post_transfer(
                    db=db,
                    user_id=user.id,
                    transfer_id=tr.id,
                    source_account_id=liab_acc_resp.id,
                    source_account_type="loan_liability",
                    dest_account_id=disb_acc.id,
                    dest_account_type=disb_acc.account_type,
                    amount=q2(req.outstanding_principal),
                    entry_date=req.loan_start_date,
                    description=f"Loan disbursement: {req.loan_name.strip()}",
                )

            loan = Loan(
                user_id=user.id,
                liability_account_id=liab_acc_resp.id,
                linked_repayment_account_id=req.linked_repayment_account_id,
                loan_name=req.loan_name.strip(),
                lender_name=req.lender_name.strip(),
                loan_type=req.loan_type,
                original_principal=q2(req.original_principal) if req.original_principal else None,
                outstanding_principal_at_start=q2(req.outstanding_principal),
                current_outstanding_principal=q2(req.outstanding_principal),
                currency="INR",
                interest_rate=req.interest_rate,
                interest_rate_type=req.interest_rate_type,
                calculation_method=req.calculation_method,
                loan_start_date=req.loan_start_date,
                tracking_start_date=req.tracking_start_date,
                first_emi_date=req.first_emi_date,
                next_emi_due_date=req.first_emi_date,
                original_tenure_months=req.original_tenure_months,
                remaining_tenure_months=req.remaining_tenure_months,
                emi_amount=q2(emi_amt),
                emi_frequency=req.emi_frequency,
                anchor_day=req.first_emi_date.day,
                loan_reference=req.loan_reference.strip() if req.loan_reference else None,
                processing_fee=q2(req.processing_fee) if req.processing_fee is not None else None,
                prepayment_charges_info=(
                    req.prepayment_charges_info.strip() if req.prepayment_charges_info else None
                ),
                notes=req.notes.strip() if req.notes else None,
                status="active",
                reminder_enabled=req.reminder_enabled,
                reminder_days_before=req.reminder_days_before,
                notification_channels=req.notification_channels.model_dump(),
            )
            self.loan_repo.create(db, loan)

            self.loan_repo.add_rate_history(
                db,
                LoanInterestRateHistory(
                    user_id=user.id,
                    loan_id=loan.id,
                    previous_rate=None,
                    new_rate=req.interest_rate,
                    effective_date=req.tracking_start_date,
                    previous_emi=None,
                    new_emi=q2(emi_amt),
                    remaining_tenure_months=req.remaining_tenure_months,
                    reason="Initial loan registration terms",
                ),
            )

            self._sync_installments_from_date(
                db,
                loan,
                start_installment_number=1,
                first_due_date=req.first_emi_date,
                periods=req.remaining_tenure_months,
            )
            db.add(loan)
            self.reminder_service.sync_reminders_for_loan(db, loan, user_timezone=tz)

            db.commit()
            loaded = self.loan_repo.get_by_id(db, loan.id, user.id)
            assert loaded is not None
            return self._to_response(loaded, user_today)
        except Exception:
            db.rollback()
            raise

    def list_loans(
        self,
        db: Session,
        user: User,
        status_filter: str | None = None,
        loan_type: str | None = None,
        search: str | None = None,
        sort_by: str = "next_due_asc",
        include_archived: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> LoanListResponse:
        user_today = resolve_user_today(self._user_tz(user))
        raw = self.loan_repo.list_by_user(
            db,
            user.id,
            include_archived=include_archived,
            loan_type=loan_type,
            status_filter=status_filter,
            search=search,
        )
        items = [self._to_response(ln, user_today) for ln in raw]
        if status_filter == "overdue":
            items = [ln for ln in items if ln.derived_status == "overdue"]

        if sort_by == "principal_desc":
            items.sort(key=lambda ln: ln.current_outstanding_principal, reverse=True)
        elif sort_by == "emi_desc":
            items.sort(key=lambda ln: ln.emi_amount, reverse=True)
        elif sort_by == "name_asc":
            items.sort(key=lambda ln: ln.loan_name.lower())
        else:
            items.sort(key=lambda ln: ln.next_emi_due_date or dt.date.max)

        total = len(items)
        total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
        offset = max(0, (page - 1) * page_size)
        return LoanListResponse(
            items=items[offset : offset + page_size],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    def get_loan(self, db: Session, user: User, loan_id: uuid.UUID) -> LoanResponse:
        loan = self.loan_repo.get_by_id(db, loan_id, user.id)
        if not loan:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan not found.")
        return self._to_response(loan, resolve_user_today(self._user_tz(user)))

    def update_loan(
        self, db: Session, user: User, loan_id: uuid.UUID, req: LoanUpdateRequest
    ) -> LoanResponse:
        loan = self.loan_repo.get_by_id(db, loan_id, user.id)
        if not loan:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan not found.")
        if loan.status == "archived":
            raise HTTPException(status_code=400, detail="Archived loans cannot be edited.")

        if req.loan_name is not None:
            stripped = req.loan_name.strip()
            if not stripped:
                raise HTTPException(status_code=400, detail="Loan name cannot be blank.")
            loan.loan_name = stripped
        if req.lender_name is not None:
            loan.lender_name = req.lender_name.strip()
        if req.loan_type is not None:
            loan.loan_type = req.loan_type
        if req.linked_repayment_account_id is not None:
            acc = self.account_repo.get_by_id(db, req.linked_repayment_account_id, user.id)
            if not acc or acc.status != "active":
                raise HTTPException(status_code=400, detail="Linked repayment account invalid.")
            loan.linked_repayment_account_id = req.linked_repayment_account_id
        if req.loan_reference is not None:
            loan.loan_reference = req.loan_reference.strip() or None
        if req.prepayment_charges_info is not None:
            loan.prepayment_charges_info = req.prepayment_charges_info.strip() or None
        if req.notes is not None:
            loan.notes = req.notes.strip() or None
        if req.reminder_enabled is not None:
            loan.reminder_enabled = req.reminder_enabled
        if req.reminder_days_before is not None:
            loan.reminder_days_before = sorted(
                {d for d in req.reminder_days_before if 0 <= d <= 60}, reverse=True
            ) or [5, 3, 1, 0]
        if req.notification_channels is not None:
            loan.notification_channels = req.notification_channels.model_dump()

        db.add(loan)
        self.reminder_service.sync_reminders_for_loan(db, loan, user_timezone=self._user_tz(user))
        db.commit()
        db.expire_all()
        return self.get_loan(db, user, loan.id)

    def archive_loan(self, db: Session, user: User, loan_id: uuid.UUID) -> LoanResponse:
        loan = self.loan_repo.get_by_id(db, loan_id, user.id)
        if not loan:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan not found.")
        loan.status = "archived"
        loan.reminder_enabled = False
        db.add(loan)
        self.reminder_service.sync_reminders_for_loan(db, loan, user_timezone=self._user_tz(user))
        db.commit()
        db.expire_all()
        return self.get_loan(db, user, loan.id)

    def _regenerate_future_unpaid_installments(
        self,
        db: Session,
        loan: Loan,
        periods: int,
        user_today: dt.date,
    ) -> None:
        paid_nums = []
        next_due = loan.next_emi_due_date or user_today
        first_unpaid_due: dt.date | None = None

        for inst in sorted(loan.installments or [], key=lambda i: i.installment_number):
            if inst.status in {"paid", "partially_paid"}:
                paid_nums.append(inst.installment_number)
            elif inst.status == "upcoming":
                if first_unpaid_due is None:
                    first_unpaid_due = inst.due_date
                inst.status = "cancelled"
                db.add(inst)
        db.flush()

        start_num = (max(paid_nums) + 1) if paid_nums else 1
        start_due = first_unpaid_due or next_due
        if loan.current_outstanding_principal <= Decimal("0.00"):
            loan.status = "closed"
            loan.next_emi_due_date = None
            loan.remaining_tenure_months = 0
            loan.reminder_enabled = False
            return

        self._sync_installments_from_date(
            db,
            loan,
            start_installment_number=start_num,
            first_due_date=start_due,
            periods=max(1, periods),
        )

    def revise_interest_rate(
        self, db: Session, user: User, loan_id: uuid.UUID, req: LoanInterestRateRevisionRequest
    ) -> LoanResponse:
        loan = self.loan_repo.get_by_id(db, loan_id, user.id)
        if not loan:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan not found.")
        if loan.status in {"closed", "archived"}:
            raise HTTPException(status_code=400, detail="Cannot revise rate on closed/archived loan.")

        tz = self._user_tz(user)
        user_today = resolve_user_today(tz)
        prev_rate = loan.interest_rate
        prev_emi = loan.emi_amount
        unpaid_count = sum(1 for i in loan.installments if i.status == "upcoming")
        rem_periods = max(1, unpaid_count or loan.remaining_tenure_months)

        if req.policy == "adjust_tenure" and prev_emi > Decimal("0.00"):
            new_emi = prev_emi
            new_periods = solve_remaining_periods_for_emi(
                loan.current_outstanding_principal,
                req.new_rate,
                new_emi,
                loan.emi_frequency,
                loan.calculation_method,
            )
        else:
            new_emi, _, _, _ = calculate_emi_summary(
                loan.current_outstanding_principal,
                req.new_rate,
                rem_periods,
                loan.emi_frequency,
                "zero_interest" if req.new_rate == Decimal("0.000") else loan.calculation_method,
            )
            new_periods = rem_periods

        loan.interest_rate = req.new_rate
        if req.new_rate == Decimal("0.000"):
            loan.calculation_method = "zero_interest"
        loan.emi_amount = new_emi

        self.loan_repo.add_rate_history(
            db,
            LoanInterestRateHistory(
                user_id=user.id,
                loan_id=loan.id,
                previous_rate=prev_rate,
                new_rate=req.new_rate,
                effective_date=req.effective_date,
                previous_emi=prev_emi,
                new_emi=new_emi,
                remaining_tenure_months=new_periods,
                reason=req.reason.strip() if req.reason else "Interest rate revision",
            ),
        )

        self._regenerate_future_unpaid_installments(db, loan, new_periods, user_today)
        db.add(loan)
        self.reminder_service.sync_reminders_for_loan(db, loan, user_timezone=tz)
        db.commit()
        db.expire_all()
        return self.get_loan(db, user, loan.id)

    def simulate_prepayment(
        self,
        db: Session,
        user: User,
        loan_id: uuid.UUID,
        req: LoanPrepaymentScenarioRequest,
    ) -> LoanPrepaymentScenarioResponse:
        loan = self.loan_repo.get_by_id(db, loan_id, user.id)
        if not loan:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan not found.")
        user_today = resolve_user_today(self._user_tz(user))
        unpaid_count = sum(1 for i in loan.installments if i.status in {"upcoming", "partially_paid"})
        rem_periods = max(1, unpaid_count or loan.remaining_tenure_months)

        sim = simulate_prepayment_scenario(
            current_principal=loan.current_outstanding_principal,
            annual_interest_rate=loan.interest_rate,
            current_emi=loan.emi_amount,
            remaining_installments=rem_periods,
            next_due_date=loan.next_emi_due_date or user_today,
            anchor_day=loan.anchor_day,
            emi_frequency=loan.emi_frequency,
            calculation_method=loan.calculation_method,
            extra_monthly_emi=req.extra_monthly_emi,
            lump_sum_prepayment=req.lump_sum_prepayment,
            prepayment_mode=req.prepayment_mode,
            user_prepayment_fee=req.user_prepayment_fee,
        )
        return LoanPrepaymentScenarioResponse(
            is_scenario_simulation=True,
            disclaimer=(
                "Scenario calculation only — no database records, loan balances, or financial ledger "
                "entries are altered until you explicitly confirm a prepayment."
            ),
            **sim,
        )

    def record_payment(
        self,
        db: Session,
        user: User,
        loan_id: uuid.UUID,
        req: LoanPaymentCreateRequest,
    ) -> LoanResponse:
        """
        Atomically splits EMI/prepayment accounting into:
        - Principal component -> FinancialTransfer reducing payment account & loan_liability account
          (NEVER counted as an expense in Phase 4 analytics).
        - Interest component -> Expense FinancialTransaction ('Loan Interest') posted via TransactionService
          (Counted accurately as interest expense in Phase 4 analytics).
        - Optional fee -> Expense FinancialTransaction.
        """
        if req.idempotency_key:
            dup = self.loan_repo.get_payment_by_idempotency(
                db, user.id, loan_id, req.idempotency_key
            )
            if dup:
                return self.get_loan(db, user, loan_id)

        loan = self.loan_repo.get_for_update(db, loan_id, user.id)
        if not loan:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan not found.")
        if loan.status in {"closed", "archived"}:
            raise HTTPException(status_code=400, detail="Loan is already closed or archived.")

        if req.principal_paid > loan.current_outstanding_principal:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Principal paid (₹{req.principal_paid:,.2f}) cannot exceed current outstanding "
                    f"principal (₹{loan.current_outstanding_principal:,.2f})."
                ),
            )

        pay_acc = self.account_repo.get_by_id(db, req.payment_account_id, user.id)
        if not pay_acc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Payment account not found."
            )
        if pay_acc.status != "active":
            raise HTTPException(status_code=400, detail="Cannot repay from an archived account.")
        if pay_acc.account_type == "loan_liability" or pay_acc.id == loan.liability_account_id:
            raise HTTPException(status_code=400, detail="Cannot pay a loan from a loan liability account.")

        total_outflow = q2(req.principal_paid + req.interest_paid + req.fee_paid)
        if pay_acc.account_type != "credit_card" and total_outflow > pay_acc.current_balance:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Insufficient balance in '{pay_acc.name}'. Available: "
                    f"₹{pay_acc.current_balance:,.2f}, total payment: ₹{total_outflow:,.2f}."
                ),
            )

        target_inst: LoanInstallment | None = None
        if req.installment_id:
            target_inst = self.loan_repo.get_installment(db, req.installment_id, loan.id, user.id)
            if not target_inst or target_inst.status == "cancelled":
                raise HTTPException(status_code=404, detail="Target loan installment not found.")
            if target_inst.status == "paid":
                raise HTTPException(status_code=400, detail="Selected installment is already paid.")
        elif req.payment_type in {"emi", "partial"}:
            unpaid = [
                i
                for i in sorted(loan.installments, key=lambda x: x.installment_number)
                if i.status in {"upcoming", "partially_paid"}
            ]
            target_inst = unpaid[0] if unpaid else None

        tz = self._user_tz(user)
        user_today = resolve_user_today(tz)
        try:
            transfer_id: uuid.UUID | None = None
            interest_tx_id: uuid.UUID | None = None
            fee_tx_id: uuid.UUID | None = None

            # 1. Principal Repayment -> Atomic Transfer reducing loan_liability
            if req.principal_paid > Decimal("0.00"):
                tr = FinancialTransfer(
                    user_id=user.id,
                    source_account_id=pay_acc.id,
                    destination_account_id=loan.liability_account_id,
                    amount=req.principal_paid,
                    currency=loan.currency,
                    transfer_date=req.payment_date,
                    description=f"Loan Principal Repayment: {loan.loan_name}",
                    status="completed",
                )
                self.transfer_repo.create(db, tr)
                src_tx = FinancialTransaction(
                    user_id=user.id,
                    account_id=pay_acc.id,
                    transaction_type="transfer",
                    amount=req.principal_paid,
                    currency=loan.currency,
                    description=f"Principal Repayment -> {loan.loan_name}",
                    transaction_date=req.payment_date,
                    source="loan_payment",
                    external_reference=req.reference_number,
                    transfer_id=tr.id,
                )
                dst_tx = FinancialTransaction(
                    user_id=user.id,
                    account_id=loan.liability_account_id,
                    transaction_type="transfer",
                    amount=req.principal_paid,
                    currency=loan.currency,
                    description=f"Principal Reduction: {loan.loan_name}",
                    transaction_date=req.payment_date,
                    source="loan_payment",
                    transfer_id=tr.id,
                )
                self.transaction_repo.create(db, src_tx)
                self.transaction_repo.create(db, dst_tx)
                tr.source_transaction_id = src_tx.id
                tr.destination_transaction_id = dst_tx.id
                self.transfer_repo.update(db, tr)

                self.ledger_service.post_transfer(
                    db=db,
                    user_id=user.id,
                    transfer_id=tr.id,
                    source_account_id=pay_acc.id,
                    source_account_type=pay_acc.account_type,
                    dest_account_id=loan.liability_account_id,
                    dest_account_type="loan_liability",
                    amount=req.principal_paid,
                    entry_date=req.payment_date,
                    description=f"Loan principal repayment: {loan.loan_name}",
                    currency=loan.currency,
                )
                transfer_id = tr.id

            interest_cat_id = self._resolve_interest_category_id(db)

            # 2. Interest Payment -> Expense Transaction (counted in analytics!)
            if req.interest_paid > Decimal("0.00"):
                int_tx = self.transaction_service.create_transaction(
                    db=db,
                    user=user,
                    req=TransactionCreateRequest(
                        account_id=pay_acc.id,
                        transaction_type="expense",
                        amount=req.interest_paid,
                        currency=loan.currency,
                        category_id=interest_cat_id,
                        description=f"Loan Interest: {loan.loan_name}",
                        merchant_payee=loan.lender_name,
                        transaction_date=req.payment_date,
                        notes=req.notes or f"{req.payment_type.upper()} interest component",
                    ),
                    source="loan_payment",
                    commit=False,
                )
                interest_tx_id = int_tx.id

            # 3. Optional Lender Fee -> Separate Expense Transaction
            if req.fee_paid > Decimal("0.00"):
                fee_tx = self.transaction_service.create_transaction(
                    db=db,
                    user=user,
                    req=TransactionCreateRequest(
                        account_id=pay_acc.id,
                        transaction_type="expense",
                        amount=req.fee_paid,
                        currency=loan.currency,
                        category_id=interest_cat_id,
                        description=f"Loan Fee/Charges: {loan.loan_name}",
                        merchant_payee=loan.lender_name,
                        transaction_date=req.payment_date,
                        notes=req.notes or "User-supplied prepayment/loan fee",
                    ),
                    source="loan_payment",
                    commit=False,
                )
                fee_tx_id = fee_tx.id

            db.refresh(pay_acc)
            if pay_acc.account_type != "credit_card" and pay_acc.current_balance < Decimal("0.00"):
                raise HTTPException(
                    status_code=400, detail=f"Repayment would make '{pay_acc.name}' balance negative."
                )

            payment = LoanPayment(
                user_id=user.id,
                loan_id=loan.id,
                installment_id=target_inst.id if target_inst else None,
                payment_account_id=pay_acc.id,
                principal_transfer_id=transfer_id,
                interest_transaction_id=interest_tx_id,
                fee_transaction_id=fee_tx_id,
                payment_type=req.payment_type,
                payment_date=req.payment_date,
                principal_paid=req.principal_paid,
                interest_paid=req.interest_paid,
                fee_paid=req.fee_paid,
                total_paid=total_outflow,
                reference_number=req.reference_number.strip() if req.reference_number else None,
                payment_status="completed",
                notes=req.notes.strip() if req.notes else None,
                idempotency_key=req.idempotency_key,
            )
            self.loan_repo.create_payment(db, payment)

            # Sync loan outstanding principal directly from ledger
            new_principal = self.ledger_repo.calculate_account_balance(
                db, loan.liability_account_id, "loan_liability"
            )
            loan.current_outstanding_principal = max(Decimal("0.00"), q2(new_principal))

            if target_inst is not None and req.payment_type in {"emi", "partial"}:
                target_inst.principal_paid = q2(
                    Decimal(target_inst.principal_paid) + req.principal_paid
                )
                target_inst.interest_paid = q2(
                    Decimal(target_inst.interest_paid) + req.interest_paid
                )
                settled = req.payment_type == "emi" or (
                    target_inst.principal_paid + target_inst.interest_paid >= target_inst.emi_amount
                )
                if settled:
                    target_inst.status = "paid"
                    target_inst.paid_date = req.payment_date
                else:
                    target_inst.status = "partially_paid"
                db.add(target_inst)

                # Advance next_emi_due_date to next unpaid installment
                next_unpaid = [
                    i
                    for i in sorted(loan.installments, key=lambda x: x.installment_number)
                    if i.id != target_inst.id and i.status in {"upcoming", "partially_paid"}
                ]
                loan.next_emi_due_date = next_unpaid[0].due_date if next_unpaid else None
                loan.remaining_tenure_months = len(next_unpaid)

            if loan.current_outstanding_principal <= Decimal("0.00"):
                for inst in loan.installments:
                    if inst.status in {"upcoming", "partially_paid"}:
                        inst.status = "cancelled"
                        db.add(inst)
                loan.status = "closed"
                loan.next_emi_due_date = None
                loan.remaining_tenure_months = 0
                loan.reminder_enabled = False
            elif req.payment_type == "prepayment":
                unpaid_cnt = sum(1 for i in loan.installments if i.status == "upcoming")
                rem_periods = max(1, unpaid_cnt or loan.remaining_tenure_months)
                if req.prepayment_mode == "reduce_emi":
                    new_emi, _, _, _ = calculate_emi_summary(
                        loan.current_outstanding_principal,
                        loan.interest_rate,
                        rem_periods,
                        loan.emi_frequency,
                        loan.calculation_method,
                    )
                    loan.emi_amount = new_emi
                    new_periods = rem_periods
                else:
                    new_periods = solve_remaining_periods_for_emi(
                        loan.current_outstanding_principal,
                        loan.interest_rate,
                        loan.emi_amount,
                        loan.emi_frequency,
                        loan.calculation_method,
                    )
                self._regenerate_future_unpaid_installments(db, loan, new_periods, user_today)

            db.add(loan)
            self.reminder_service.sync_reminders_for_loan(db, loan, user_timezone=tz)

            self.bill_repo.create_notification(
                db,
                Notification(
                    user_id=user.id,
                    title=f"Loan Repayment Recorded: {loan.loan_name}",
                    message=(
                        f"Recorded {req.payment_type.upper()} of ₹{total_outflow:,.2f} "
                        f"(Principal ₹{req.principal_paid:,.2f}, Interest ₹{req.interest_paid:,.2f}). "
                        f"Remaining principal: ₹{loan.current_outstanding_principal:,.2f}."
                    ),
                    notification_type="loan_payment_recorded",
                    related_loan_id=loan.id,
                    dedupe_key=f"loan-pay:{payment.id}",
                ),
            )
            db.commit()
            return self.get_loan(db, user, loan.id)
        except Exception:
            db.rollback()
            raise

    def link_existing_transaction(
        self, db: Session, user: User, loan_id: uuid.UUID, req: LoanPaymentLinkRequest
    ) -> LoanResponse:
        loan = self.loan_repo.get_for_update(db, loan_id, user.id)
        if not loan:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan not found.")
        tx = self.transaction_repo.get_by_id(db, req.transaction_id, user.id)
        if not tx:
            raise HTTPException(status_code=404, detail="Transaction not found.")
        if self.loan_repo.get_payment_by_linked_tx(db, tx.id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This transaction is already linked to a loan payment.",
            )
        if (req.principal_component + req.interest_component) != Decimal(tx.amount):
            raise HTTPException(
                status_code=400,
                detail="Principal + Interest components must equal the linked transaction amount.",
            )
        if req.principal_component > loan.current_outstanding_principal:
            raise HTTPException(
                status_code=400,
                detail="Principal component cannot exceed current outstanding principal.",
            )

        try:
            # Record balancing liability reduction journal entry without creating duplicate bank outflow
            if req.principal_component > Decimal("0.00"):
                tr = FinancialTransfer(
                    user_id=user.id,
                    source_account_id=tx.account_id,
                    destination_account_id=loan.liability_account_id,
                    amount=req.principal_component,
                    currency=tx.currency,
                    transfer_date=tx.transaction_date,
                    description=f"Linked Principal Allocation: {loan.loan_name}",
                    status="completed",
                )
                self.transfer_repo.create(db, tr)
                # Reduce only loan_liability account balance cleanly via transfer-style journal entry where bank already reflected tx?
                # No — avoid double-debiting bank! Just post liability opening/adjustment equity offset directly on liability account,
                # OR enforce bank account untouched by crediting nothing on asset and offsetting equity!
                from app.models.finance import LedgerEntry, LedgerJournal

                j = LedgerJournal(
                    user_id=user.id,
                    journal_type="transfer",
                    reference=f"LNLINK-{tx.id.hex[:8]}",
                    description=f"Linked principal allocation for {loan.loan_name}",
                    entry_date=tx.transaction_date,
                )
                db.add(j)
                db.flush()
                db.add(
                    LedgerEntry(
                        journal_id=j.id,
                        account_id=loan.liability_account_id,
                        entry_type="debit",
                        amount=req.principal_component,
                        currency=tx.currency,
                        description="Linked principal reduction",
                    )
                )
                db.add(
                    LedgerEntry(
                        journal_id=j.id,
                        account_id=None,
                        entry_type="credit",
                        amount=req.principal_component,
                        currency=tx.currency,
                        description="Linked principal equity offset",
                    )
                )
                self.ledger_service.recalculate_and_sync_account_balance(
                    db, loan.liability_account_id, "loan_liability"
                )

            payment = LoanPayment(
                user_id=user.id,
                loan_id=loan.id,
                installment_id=req.installment_id,
                payment_account_id=tx.account_id,
                linked_transaction_id=tx.id,
                payment_type="linked_transaction",
                payment_date=tx.transaction_date,
                principal_paid=req.principal_component,
                interest_paid=req.interest_component,
                fee_paid=Decimal("0.00"),
                total_paid=tx.amount,
                reference_number=tx.external_reference,
                payment_status="completed",
                notes=req.notes or f"Linked tx: {tx.description}",
            )
            self.loan_repo.create_payment(db, payment)

            new_principal = self.ledger_repo.calculate_account_balance(
                db, loan.liability_account_id, "loan_liability"
            )
            loan.current_outstanding_principal = max(Decimal("0.00"), q2(new_principal))
            if loan.current_outstanding_principal <= Decimal("0.00"):
                loan.status = "closed"
                loan.next_emi_due_date = None
                loan.remaining_tenure_months = 0
                loan.reminder_enabled = False
            db.add(loan)
            self.reminder_service.sync_reminders_for_loan(db, loan, user_timezone=self._user_tz(user))
            db.commit()
            return self.get_loan(db, user, loan.id)
        except Exception:
            db.rollback()
            raise

    def reverse_payment(
        self,
        db: Session,
        user: User,
        loan_id: uuid.UUID,
        payment_id: uuid.UUID,
        req: LoanPaymentReverseRequest,
    ) -> LoanResponse:
        payment = self.loan_repo.get_payment_by_id(db, payment_id, loan_id, user.id)
        if not payment:
            raise HTTPException(status_code=404, detail="Loan payment not found.")
        if payment.payment_status == "reversed":
            raise HTTPException(status_code=400, detail="Loan payment is already reversed.")
        loan = self.loan_repo.get_for_update(db, loan_id, user.id)
        assert loan is not None

        try:
            if payment.principal_transfer_id and payment.payment_account_id:
                pay_acc = self.account_repo.get_by_id(db, payment.payment_account_id, user.id)
                if pay_acc:
                    self.ledger_service.reverse_transfer_journal(
                        db,
                        payment.principal_transfer_id,
                        pay_acc.id,
                        pay_acc.account_type,
                        loan.liability_account_id,
                        "loan_liability",
                    )
            if payment.interest_transaction_id and payment.payment_account_id:
                pay_acc = self.account_repo.get_by_id(db, payment.payment_account_id, user.id)
                if pay_acc:
                    self.ledger_service.reverse_transaction_journal(
                        db, payment.interest_transaction_id, pay_acc.id, pay_acc.account_type
                    )
            if payment.fee_transaction_id and payment.payment_account_id:
                pay_acc = self.account_repo.get_by_id(db, payment.fee_transaction_id, user.id)
                if pay_acc:
                    self.ledger_service.reverse_transaction_journal(
                        db, payment.fee_transaction_id, pay_acc.id, pay_acc.account_type
                    )

            payment.payment_status = "reversed"
            payment.reversal_reason = req.reason.strip()
            db.add(payment)

            if payment.installment_id:
                inst = self.loan_repo.get_installment(db, payment.installment_id, loan.id, user.id)
                if inst:
                    inst.principal_paid = max(
                        Decimal("0.00"), q2(Decimal(inst.principal_paid) - Decimal(payment.principal_paid))
                    )
                    inst.interest_paid = max(
                        Decimal("0.00"), q2(Decimal(inst.interest_paid) - Decimal(payment.interest_paid))
                    )
                    inst.status = (
                        "partially_paid"
                        if (inst.principal_paid + inst.interest_paid) > Decimal("0.00")
                        else "upcoming"
                    )
                    inst.paid_date = None
                    db.add(inst)

            new_principal = self.ledger_repo.calculate_account_balance(
                db, loan.liability_account_id, "loan_liability"
            )
            loan.current_outstanding_principal = max(Decimal("0.00"), q2(new_principal))
            if loan.status == "closed" and loan.current_outstanding_principal > Decimal("0.00"):
                loan.status = "active"
            db.add(loan)
            self.reminder_service.sync_reminders_for_loan(db, loan, user_timezone=self._user_tz(user))
            db.commit()
            return self.get_loan(db, user, loan.id)
        except Exception:
            db.rollback()
            raise

    def list_payments(
        self, db: Session, user: User, loan_id: uuid.UUID | None = None
    ) -> LoanPaymentListResponse:
        if loan_id is not None:
            if not self.loan_repo.get_by_id(db, loan_id, user.id):
                raise HTTPException(status_code=404, detail="Loan not found.")
        rows = self.loan_repo.list_payments(db, user.id, loan_id=loan_id)
        return LoanPaymentListResponse(items=[self._payment_to_response(p) for p in rows], total=len(rows))

    def get_overview(self, db: Session, user: User) -> LoanOverviewResponse:
        user_today = resolve_user_today(self._user_tz(user))
        raw = self.loan_repo.list_by_user(db, user.id, include_archived=False)
        loans = [self._to_response(ln, user_today) for ln in raw]

        active = [ln for ln in loans if ln.status == "active"]
        closed = [ln for ln in loans if ln.status == "closed"]
        overdue_loans = [ln for ln in loans if ln.derived_status == "overdue"]

        total_out = q2(sum((ln.current_outstanding_principal for ln in active), Decimal("0.00")))
        known_orig = [ln.original_principal for ln in loans if ln.original_principal is not None]
        orig_sum = q2(sum(known_orig, Decimal("0.00"))) if len(known_orig) == len(loans) and loans else None
        monthly_emi = q2(sum((ln.emi_amount for ln in active if ln.emi_frequency == "monthly"), Decimal("0.00")))
        prin_rep = q2(sum((ln.total_principal_repaid for ln in loans), Decimal("0.00")))
        int_paid = q2(sum((ln.total_interest_paid for ln in loans), Decimal("0.00")))
        overdue_inst_cnt = sum(ln.overdue_installments_count for ln in loans)

        next_due = sorted(
            [ln for ln in active if ln.next_emi_due_date is not None],
            key=lambda ln: ln.next_emi_due_date or dt.date.max,
        )
        return LoanOverviewResponse(
            active_loans_count=len(active),
            closed_loans_count=len(closed),
            overdue_loans_count=len(overdue_loans),
            overdue_installments_count=overdue_inst_cnt,
            total_outstanding_principal=total_out,
            total_original_principal_known=orig_sum,
            total_monthly_emi_commitment=monthly_emi,
            total_principal_repaid=prin_rep,
            total_interest_paid=int_paid,
            next_emi_due_loan=next_due[0] if next_due else None,
        )

    def get_analytics(self, db: Session, user: User) -> LoanAnalyticsResponse:
        user_today = resolve_user_today(self._user_tz(user))
        raw = self.loan_repo.list_by_user(db, user.id, include_archived=False)
        loans = [self._to_response(ln, user_today) for ln in raw]

        total_out = q2(sum((ln.current_outstanding_principal for ln in loans if ln.status != "closed"), Decimal("0.00")))
        total_prin = q2(sum((ln.total_principal_repaid for ln in loans), Decimal("0.00")))
        total_int = q2(sum((ln.total_interest_paid for ln in loans), Decimal("0.00")))
        total_actual = q2(total_prin + total_int)

        proj_rem_int = Decimal("0.00")
        maturity_dates: list[dt.date] = []
        by_loan: list[LoanBreakdownItem] = []
        trend_map: dict[str, dict[str, Decimal]] = defaultdict(
            lambda: {"principal": Decimal("0.00"), "interest": Decimal("0.00")}
        )

        for ln in loans:
            if ln.status != "closed":
                proj_rem_int += q2(
                    sum(
                        (
                            i.interest_component
                            for i in ln.installments
                            if i.status in {"upcoming", "partially_paid"}
                        ),
                        Decimal("0.00"),
                    )
                )
                if ln.maturity_date:
                    maturity_dates.append(ln.maturity_date)

            by_loan.append(
                LoanBreakdownItem(
                    loan_id=ln.id,
                    loan_name=ln.loan_name,
                    lender_name=ln.lender_name,
                    loan_type=ln.loan_type,
                    outstanding_principal=ln.current_outstanding_principal,
                    principal_repaid=ln.total_principal_repaid,
                    interest_paid=ln.total_interest_paid,
                    emi_amount=ln.emi_amount,
                    progress_pct=ln.repayment_progress_pct,
                    maturity_date=ln.maturity_date,
                    status=ln.derived_status,
                )
            )
            for p in ln.payments:
                if p.payment_status != "completed":
                    continue
                ym = p.payment_date.strftime("%Y-%m")
                trend_map[ym]["principal"] += Decimal(p.principal_paid)
                trend_map[ym]["interest"] += Decimal(p.interest_paid)

        prin_share = q2((total_prin / total_actual) * Decimal("100")) if total_actual > 0 else Decimal("0.00")
        int_share = q2(Decimal("100.00") - prin_share) if total_actual > 0 else Decimal("0.00")
        monthly_emi = q2(
            sum((ln.emi_amount for ln in loans if ln.status == "active" and ln.emi_frequency == "monthly"), Decimal("0.00"))
        )

        trend = []
        for ym in sorted(trend_map.keys())[-12:]:
            dt_m = dt.datetime.strptime(ym, "%Y-%m").date()
            trend.append(
                {
                    "month": ym,
                    "label": dt_m.strftime("%b %Y"),
                    "principal": float(q2(trend_map[ym]["principal"])),
                    "interest": float(q2(trend_map[ym]["interest"])),
                }
            )

        return LoanAnalyticsResponse(
            total_outstanding_principal=total_out,
            total_principal_repaid=total_prin,
            total_interest_paid=total_int,
            total_repayment_actual=total_actual,
            projected_remaining_interest=q2(proj_rem_int),
            monthly_emi_commitment=monthly_emi,
            estimated_latest_maturity_date=max(maturity_dates) if maturity_dates else None,
            principal_share_pct=prin_share,
            interest_share_pct=int_share,
            by_loan=by_loan,
            repayment_trend=trend,
        )
