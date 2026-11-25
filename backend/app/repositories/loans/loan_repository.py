import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.loans import (
    Loan,
    LoanInstallment,
    LoanInterestRateHistory,
    LoanPayment,
)


class LoanRepository:
    """Multi-tenant scoped PostgreSQL repository for Phase 6 Loans & EMIs."""

    def create(self, db: Session, loan: Loan) -> Loan:
        db.add(loan)
        db.flush()
        return loan

    def get_by_id(self, db: Session, loan_id: uuid.UUID, user_id: uuid.UUID) -> Loan | None:
        stmt = (
            select(Loan)
            .options(
                joinedload(Loan.liability_account),
                joinedload(Loan.linked_repayment_account),
                joinedload(Loan.installments),
                joinedload(Loan.rate_history),
                joinedload(Loan.payments).joinedload(LoanPayment.payment_account),
                joinedload(Loan.reminders),
            )
            .where(Loan.id == loan_id, Loan.user_id == user_id)
        )
        return db.execute(stmt).unique().scalar_one_or_none()

    def get_for_update(self, db: Session, loan_id: uuid.UUID, user_id: uuid.UUID) -> Loan | None:
        return db.execute(
            select(Loan).where(Loan.id == loan_id, Loan.user_id == user_id).with_for_update()
        ).scalar_one_or_none()

    def list_by_user(
        self,
        db: Session,
        user_id: uuid.UUID,
        include_archived: bool = False,
        loan_type: str | None = None,
        status_filter: str | None = None,
        search: str | None = None,
    ) -> list[Loan]:
        stmt = (
            select(Loan)
            .options(
                joinedload(Loan.liability_account),
                joinedload(Loan.linked_repayment_account),
                joinedload(Loan.installments),
                joinedload(Loan.rate_history),
                joinedload(Loan.payments).joinedload(LoanPayment.payment_account),
                joinedload(Loan.reminders),
            )
            .where(Loan.user_id == user_id)
        )
        if not include_archived and status_filter != "archived":
            stmt = stmt.where(Loan.status != "archived")
        if loan_type:
            stmt = stmt.where(Loan.loan_type == loan_type)
        if status_filter and status_filter not in {"all", "overdue"}:
            stmt = stmt.where(Loan.status == status_filter)
        if search and search.strip():
            term = f"%{search.strip()}%"
            stmt = stmt.where(
                Loan.loan_name.ilike(term)
                | Loan.lender_name.ilike(term)
                | Loan.loan_reference.ilike(term)
            )
        return list(db.execute(stmt).unique().scalars().all())

    def add_installment(self, db: Session, inst: LoanInstallment) -> LoanInstallment:
        db.add(inst)
        db.flush()
        return inst

    def get_installment(
        self, db: Session, inst_id: uuid.UUID, loan_id: uuid.UUID, user_id: uuid.UUID
    ) -> LoanInstallment | None:
        return db.execute(
            select(LoanInstallment).where(
                LoanInstallment.id == inst_id,
                LoanInstallment.loan_id == loan_id,
                LoanInstallment.user_id == user_id,
            )
        ).scalar_one_or_none()

    def add_rate_history(
        self, db: Session, hist: LoanInterestRateHistory
    ) -> LoanInterestRateHistory:
        db.add(hist)
        db.flush()
        return hist

    def get_payment_by_id(
        self, db: Session, payment_id: uuid.UUID, loan_id: uuid.UUID, user_id: uuid.UUID
    ) -> LoanPayment | None:
        return db.execute(
            select(LoanPayment).where(
                LoanPayment.id == payment_id,
                LoanPayment.loan_id == loan_id,
                LoanPayment.user_id == user_id,
            )
        ).scalar_one_or_none()

    def get_payment_by_idempotency(
        self, db: Session, user_id: uuid.UUID, loan_id: uuid.UUID, idempotency_key: str
    ) -> LoanPayment | None:
        return db.execute(
            select(LoanPayment).where(
                LoanPayment.user_id == user_id,
                LoanPayment.loan_id == loan_id,
                LoanPayment.idempotency_key == idempotency_key,
            )
        ).scalar_one_or_none()

    def get_payment_by_linked_tx(
        self, db: Session, transaction_id: uuid.UUID
    ) -> LoanPayment | None:
        return db.execute(
            select(LoanPayment).where(
                LoanPayment.linked_transaction_id == transaction_id,
                LoanPayment.payment_status == "completed",
            )
        ).scalar_one_or_none()

    def create_payment(self, db: Session, payment: LoanPayment) -> LoanPayment:
        db.add(payment)
        db.flush()
        return payment

    def list_payments(
        self,
        db: Session,
        user_id: uuid.UUID,
        loan_id: uuid.UUID | None = None,
        limit: int = 200,
    ) -> list[LoanPayment]:
        stmt = (
            select(LoanPayment)
            .options(
                joinedload(LoanPayment.loan),
                joinedload(LoanPayment.payment_account),
            )
            .where(LoanPayment.user_id == user_id)
        )
        if loan_id is not None:
            stmt = stmt.where(LoanPayment.loan_id == loan_id)
        stmt = stmt.order_by(
            LoanPayment.payment_date.desc(), LoanPayment.created_at.desc()
        ).limit(limit)
        return list(db.execute(stmt).scalars().all())
