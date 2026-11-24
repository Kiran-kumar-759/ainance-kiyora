import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.finance import FinancialCategory


class CategoryRepository:
    """Repository for transaction categories supporting both system defaults and user custom categories."""

    def get_by_id(
        self, db: Session, category_id: uuid.UUID, user_id: uuid.UUID
    ) -> FinancialCategory | None:
        stmt = select(FinancialCategory).where(
            FinancialCategory.id == category_id,
            or_(
                FinancialCategory.user_id == user_id,
                FinancialCategory.user_id.is_(None),
            ),
        )
        return db.execute(stmt).scalar_one_or_none()

    def list_accessible_categories(
        self, db: Session, user_id: uuid.UUID, category_type: str | None = None
    ) -> list[FinancialCategory]:
        stmt = select(FinancialCategory).where(
            or_(
                FinancialCategory.user_id == user_id,
                FinancialCategory.user_id.is_(None),
            )
        )
        if category_type:
            stmt = stmt.where(FinancialCategory.category_type == category_type)
        stmt = stmt.order_by(FinancialCategory.is_system.desc(), FinancialCategory.name.asc())
        return list(db.execute(stmt).scalars().all())

    def get_user_category_by_name(
        self, db: Session, user_id: uuid.UUID, name: str, category_type: str
    ) -> FinancialCategory | None:
        stmt = select(FinancialCategory).where(
            FinancialCategory.user_id == user_id,
            FinancialCategory.name.ilike(name),
            FinancialCategory.category_type == category_type,
        )
        return db.execute(stmt).scalar_one_or_none()

    def get_system_category_by_name(
        self, db: Session, name: str, category_type: str
    ) -> FinancialCategory | None:
        stmt = select(FinancialCategory).where(
            FinancialCategory.user_id.is_(None),
            FinancialCategory.name.ilike(name),
            FinancialCategory.category_type == category_type,
        )
        return db.execute(stmt).scalar_one_or_none()

    def create(self, db: Session, category: FinancialCategory) -> FinancialCategory:
        db.add(category)
        db.flush()
        return category

    def update(self, db: Session, category: FinancialCategory) -> FinancialCategory:
        db.add(category)
        db.flush()
        return category

    def delete(self, db: Session, category: FinancialCategory) -> None:
        db.delete(category)
        db.flush()
