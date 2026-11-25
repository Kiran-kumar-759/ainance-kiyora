import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.subscriptions import (
    Subscription,
    SubscriptionCandidateDecision,
    SubscriptionPayment,
    SubscriptionPriceHistory,
)


class SubscriptionRepository:
    """Multi-tenant scoped PostgreSQL repository for Phase 6 Subscriptions."""

    def create(self, db: Session, sub: Subscription) -> Subscription:
        db.add(sub)
        db.flush()
        return sub

    def get_by_id(
        self, db: Session, sub_id: uuid.UUID, user_id: uuid.UUID
    ) -> Subscription | None:
        stmt = (
            select(Subscription)
            .options(
                joinedload(Subscription.financial_category),
                joinedload(Subscription.linked_account),
                joinedload(Subscription.price_history),
                joinedload(Subscription.payments).joinedload(SubscriptionPayment.financial_account),
                joinedload(Subscription.reminders),
            )
            .where(Subscription.id == sub_id, Subscription.user_id == user_id)
        )
        return db.execute(stmt).unique().scalar_one_or_none()

    def get_for_update(
        self, db: Session, sub_id: uuid.UUID, user_id: uuid.UUID
    ) -> Subscription | None:
        stmt = (
            select(Subscription)
            .where(Subscription.id == sub_id, Subscription.user_id == user_id)
            .with_for_update()
        )
        return db.execute(stmt).scalar_one_or_none()

    def list_by_user(
        self,
        db: Session,
        user_id: uuid.UUID,
        include_archived: bool = False,
        category: str | None = None,
        status_filter: str | None = None,
        search: str | None = None,
    ) -> list[Subscription]:
        stmt = (
            select(Subscription)
            .options(
                joinedload(Subscription.financial_category),
                joinedload(Subscription.linked_account),
                joinedload(Subscription.price_history),
                joinedload(Subscription.payments).joinedload(SubscriptionPayment.financial_account),
                joinedload(Subscription.reminders),
            )
            .where(Subscription.user_id == user_id)
        )
        if not include_archived and status_filter != "archived":
            stmt = stmt.where(Subscription.status != "archived")
        if category:
            stmt = stmt.where(Subscription.category == category)
        if status_filter and status_filter != "all":
            stmt = stmt.where(Subscription.status == status_filter)
        if search and search.strip():
            term = f"%{search.strip()}%"
            stmt = stmt.where(
                Subscription.subscription_name.ilike(term)
                | Subscription.provider_name.ilike(term)
                | Subscription.plan_name.ilike(term)
            )
        return list(db.execute(stmt).unique().scalars().all())

    def add_price_history(
        self, db: Session, hist: SubscriptionPriceHistory
    ) -> SubscriptionPriceHistory:
        db.add(hist)
        db.flush()
        return hist

    def get_payment_by_id(
        self, db: Session, payment_id: uuid.UUID, sub_id: uuid.UUID, user_id: uuid.UUID
    ) -> SubscriptionPayment | None:
        return db.execute(
            select(SubscriptionPayment).where(
                SubscriptionPayment.id == payment_id,
                SubscriptionPayment.subscription_id == sub_id,
                SubscriptionPayment.user_id == user_id,
            )
        ).scalar_one_or_none()

    def get_payment_by_idempotency(
        self, db: Session, user_id: uuid.UUID, sub_id: uuid.UUID, idempotency_key: str
    ) -> SubscriptionPayment | None:
        return db.execute(
            select(SubscriptionPayment).where(
                SubscriptionPayment.user_id == user_id,
                SubscriptionPayment.subscription_id == sub_id,
                SubscriptionPayment.idempotency_key == idempotency_key,
            )
        ).scalar_one_or_none()

    def get_payment_by_transaction(
        self, db: Session, transaction_id: uuid.UUID
    ) -> SubscriptionPayment | None:
        return db.execute(
            select(SubscriptionPayment).where(
                SubscriptionPayment.transaction_id == transaction_id,
                SubscriptionPayment.payment_status == "completed",
            )
        ).scalar_one_or_none()

    def create_payment(self, db: Session, payment: SubscriptionPayment) -> SubscriptionPayment:
        db.add(payment)
        db.flush()
        return payment

    def list_payments(
        self,
        db: Session,
        user_id: uuid.UUID,
        subscription_id: uuid.UUID | None = None,
        limit: int = 200,
    ) -> list[SubscriptionPayment]:
        stmt = (
            select(SubscriptionPayment)
            .options(
                joinedload(SubscriptionPayment.subscription),
                joinedload(SubscriptionPayment.financial_account),
            )
            .where(SubscriptionPayment.user_id == user_id)
        )
        if subscription_id is not None:
            stmt = stmt.where(SubscriptionPayment.subscription_id == subscription_id)
        stmt = stmt.order_by(
            SubscriptionPayment.payment_date.desc(), SubscriptionPayment.created_at.desc()
        ).limit(limit)
        return list(db.execute(stmt).scalars().all())

    def list_linked_tx_ids(self, db: Session, user_id: uuid.UUID) -> set[uuid.UUID]:
        rows = db.execute(
            select(SubscriptionPayment.transaction_id).where(
                SubscriptionPayment.user_id == user_id,
                SubscriptionPayment.transaction_id.isnot(None),
                SubscriptionPayment.payment_status == "completed",
            )
        ).scalars()
        return {r for r in rows if r is not None}

    def list_candidate_decisions(
        self, db: Session, user_id: uuid.UUID
    ) -> dict[str, SubscriptionCandidateDecision]:
        rows = (
            db.execute(
                select(SubscriptionCandidateDecision).where(
                    SubscriptionCandidateDecision.user_id == user_id
                )
            )
            .scalars()
            .all()
        )
        return {r.merchant_key: r for r in rows}

    def upsert_candidate_decision(
        self,
        db: Session,
        user_id: uuid.UUID,
        merchant_key: str,
        decision: str,
        linked_subscription_id: uuid.UUID | None = None,
    ) -> SubscriptionCandidateDecision:
        existing = db.execute(
            select(SubscriptionCandidateDecision).where(
                SubscriptionCandidateDecision.user_id == user_id,
                SubscriptionCandidateDecision.merchant_key == merchant_key,
            )
        ).scalar_one_or_none()
        if existing:
            existing.decision = decision
            existing.linked_subscription_id = linked_subscription_id
            db.add(existing)
            db.flush()
            return existing
        rec = SubscriptionCandidateDecision(
            user_id=user_id,
            merchant_key=merchant_key,
            decision=decision,
            linked_subscription_id=linked_subscription_id,
        )
        db.add(rec)
        db.flush()
        return rec
