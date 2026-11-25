import datetime as dt
import uuid

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session, joinedload

from app.models.bills import (
    Bill,
    BillDocument,
    BillPayment,
    BillRecurrenceSchedule,
    BillReminder,
    Notification,
)


class BillRepository:
    """PostgreSQL repository for bills, schedules, payments, reminders, documents, and notifications."""

    def create_schedule(
        self, db: Session, schedule: BillRecurrenceSchedule
    ) -> BillRecurrenceSchedule:
        db.add(schedule)
        db.flush()
        return schedule

    def get_schedule(
        self, db: Session, schedule_id: uuid.UUID, user_id: uuid.UUID
    ) -> BillRecurrenceSchedule | None:
        return db.execute(
            select(BillRecurrenceSchedule).where(
                BillRecurrenceSchedule.id == schedule_id,
                BillRecurrenceSchedule.user_id == user_id,
            )
        ).scalar_one_or_none()

    def list_schedules(self, db: Session, user_id: uuid.UUID) -> list[BillRecurrenceSchedule]:
        return list(
            db.execute(
                select(BillRecurrenceSchedule)
                .where(BillRecurrenceSchedule.user_id == user_id)
                .order_by(BillRecurrenceSchedule.next_due_date.asc())
            )
            .scalars()
            .all()
        )

    def create_bill(self, db: Session, bill: Bill) -> Bill:
        db.add(bill)
        db.flush()
        return bill

    def get_bill(
        self, db: Session, bill_id: uuid.UUID, user_id: uuid.UUID
    ) -> Bill | None:
        stmt = (
            select(Bill)
            .options(
                joinedload(Bill.financial_category),
                joinedload(Bill.linked_account),
                joinedload(Bill.schedule),
                joinedload(Bill.payments).joinedload(BillPayment.financial_account),
                joinedload(Bill.reminders),
                joinedload(Bill.documents),
            )
            .where(Bill.id == bill_id, Bill.user_id == user_id)
        )
        return db.execute(stmt).unique().scalar_one_or_none()

    def get_bill_for_update(
        self, db: Session, bill_id: uuid.UUID, user_id: uuid.UUID
    ) -> Bill | None:
        stmt = (
            select(Bill)
            .where(Bill.id == bill_id, Bill.user_id == user_id)
            .with_for_update()
        )
        return db.execute(stmt).scalar_one_or_none()

    def get_occurrence_by_schedule_and_due(
        self, db: Session, schedule_id: uuid.UUID, due_date: dt.date
    ) -> Bill | None:
        return db.execute(
            select(Bill).where(
                Bill.parent_schedule_id == schedule_id,
                Bill.due_date == due_date,
            )
        ).scalar_one_or_none()

    def list_bills_by_user(
        self,
        db: Session,
        user_id: uuid.UUID,
        include_archived: bool = False,
        bill_category: str | None = None,
        bill_type: str | None = None,
        start_date: dt.date | None = None,
        end_date: dt.date | None = None,
        search: str | None = None,
    ) -> list[Bill]:
        stmt = (
            select(Bill)
            .options(
                joinedload(Bill.financial_category),
                joinedload(Bill.linked_account),
                joinedload(Bill.schedule),
                joinedload(Bill.payments).joinedload(BillPayment.financial_account),
                joinedload(Bill.reminders),
                joinedload(Bill.documents),
            )
            .where(Bill.user_id == user_id)
        )
        if not include_archived:
            stmt = stmt.where(Bill.is_active.is_(True), Bill.stored_status != "archived")
        if bill_category:
            stmt = stmt.where(Bill.bill_category == bill_category)
        if bill_type:
            stmt = stmt.where(Bill.bill_type == bill_type)
        if start_date:
            stmt = stmt.where(Bill.due_date >= start_date)
        if end_date:
            stmt = stmt.where(Bill.due_date <= end_date)
        if search and search.strip():
            pat = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    Bill.bill_name.ilike(pat),
                    Bill.provider_name.ilike(pat),
                    Bill.account_reference.ilike(pat),
                    Bill.description.ilike(pat),
                )
            )
        stmt = stmt.order_by(Bill.due_date.asc(), Bill.created_at.desc())
        return list(db.execute(stmt).unique().scalars().all())

    def get_payment_by_idempotency(
        self, db: Session, user_id: uuid.UUID, bill_id: uuid.UUID, idempotency_key: str
    ) -> BillPayment | None:
        return db.execute(
            select(BillPayment)
            .options(
                joinedload(BillPayment.bill),
                joinedload(BillPayment.financial_account),
            )
            .where(
                BillPayment.user_id == user_id,
                BillPayment.bill_id == bill_id,
                BillPayment.idempotency_key == idempotency_key,
            )
        ).scalar_one_or_none()

    def get_payment_by_transaction(
        self, db: Session, transaction_id: uuid.UUID
    ) -> BillPayment | None:
        return db.execute(
            select(BillPayment).where(BillPayment.transaction_id == transaction_id)
        ).scalar_one_or_none()

    def create_payment(self, db: Session, payment: BillPayment) -> BillPayment:
        db.add(payment)
        db.flush()
        return payment

    def list_payments(
        self, db: Session, user_id: uuid.UUID, bill_id: uuid.UUID | None = None, limit: int = 100
    ) -> list[BillPayment]:
        stmt = (
            select(BillPayment)
            .options(
                joinedload(BillPayment.bill),
                joinedload(BillPayment.financial_account),
            )
            .where(BillPayment.user_id == user_id)
        )
        if bill_id is not None:
            stmt = stmt.where(BillPayment.bill_id == bill_id)
        stmt = stmt.order_by(BillPayment.payment_date.desc(), BillPayment.created_at.desc()).limit(
            limit
        )
        return list(db.execute(stmt).scalars().all())

    def list_reminders_for_bill(self, db: Session, bill_id: uuid.UUID) -> list[BillReminder]:
        return list(
            db.execute(
                select(BillReminder)
                .where(BillReminder.bill_id == bill_id)
                .order_by(BillReminder.offset_days.desc())
            )
            .scalars()
            .all()
        )

    def get_reminder_by_idempotency_key(
        self, db: Session, idempotency_key: str
    ) -> BillReminder | None:
        return db.execute(
            select(BillReminder).where(BillReminder.idempotency_key == idempotency_key)
        ).scalar_one_or_none()

    def claim_due_reminders(
        self,
        db: Session,
        now_utc: dt.datetime,
        user_id: uuid.UUID | None = None,
        limit: int = 100,
    ) -> list[BillReminder]:
        """
        Multi-worker safe PostgreSQL claim query using FOR UPDATE SKIP LOCKED.
        Picks pending reminders due at or before now_utc, or failed reminders ready for retry.
        """
        clauses = [
            BillReminder.is_enabled.is_(True),
            or_(
                (
                    (BillReminder.delivery_status == "pending")
                    & (BillReminder.reminder_at <= now_utc)
                ),
                (
                    (BillReminder.delivery_status == "failed")
                    & (BillReminder.retry_count < BillReminder.max_retries)
                    & (
                        (BillReminder.next_retry_at.is_(None))
                        | (BillReminder.next_retry_at <= now_utc)
                    )
                ),
            ),
        ]
        if user_id is not None:
            clauses.append(BillReminder.user_id == user_id)

        stmt = (
            select(BillReminder)
            .where(*clauses)
            .order_by(BillReminder.reminder_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return list(db.execute(stmt).scalars().all())

    def create_document(self, db: Session, doc: BillDocument) -> BillDocument:
        db.add(doc)
        db.flush()
        return doc

    def get_document(
        self, db: Session, doc_id: uuid.UUID, bill_id: uuid.UUID, user_id: uuid.UUID
    ) -> BillDocument | None:
        return db.execute(
            select(BillDocument).where(
                BillDocument.id == doc_id,
                BillDocument.bill_id == bill_id,
                BillDocument.user_id == user_id,
            )
        ).scalar_one_or_none()

    def get_notification_by_dedupe(self, db: Session, dedupe_key: str) -> Notification | None:
        return db.execute(
            select(Notification).where(Notification.dedupe_key == dedupe_key)
        ).scalar_one_or_none()

    def create_notification(self, db: Session, notif: Notification) -> Notification:
        db.add(notif)
        db.flush()
        return notif

    def list_notifications(
        self, db: Session, user_id: uuid.UUID, unread_only: bool = False, limit: int = 50
    ) -> tuple[list[Notification], int, int]:
        base = select(Notification).where(Notification.user_id == user_id)
        if unread_only:
            base = base.where(Notification.is_read.is_(False))
        items = list(
            db.execute(base.order_by(Notification.created_at.desc()).limit(limit))
            .scalars()
            .all()
        )
        total = (
            db.execute(
                select(func.count(Notification.id)).where(Notification.user_id == user_id)
            ).scalar()
            or 0
        )
        unread = (
            db.execute(
                select(func.count(Notification.id)).where(
                    Notification.user_id == user_id, Notification.is_read.is_(False)
                )
            ).scalar()
            or 0
        )
        return items, int(total), int(unread)

    def get_notification(
        self, db: Session, notif_id: uuid.UUID, user_id: uuid.UUID
    ) -> Notification | None:
        return db.execute(
            select(Notification).where(
                Notification.id == notif_id, Notification.user_id == user_id
            )
        ).scalar_one_or_none()

    def mark_all_notifications_read(self, db: Session, user_id: uuid.UUID) -> int:
        now = dt.datetime.now(dt.UTC)
        res = db.execute(
            update(Notification)
            .where(Notification.user_id == user_id, Notification.is_read.is_(False))
            .values(is_read=True, read_at=now)
        )
        db.flush()
        return int(res.rowcount or 0)
