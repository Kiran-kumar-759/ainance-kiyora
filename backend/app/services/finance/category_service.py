import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.finance import FinancialCategory
from app.models.user import User
from app.repositories.finance.category_repository import CategoryRepository
from app.schemas.finance.category import (
    CategoryCreateRequest,
    CategoryResponse,
    CategoryUpdateRequest,
)

SYSTEM_CATEGORIES = [
    # Income
    {"name": "Salary", "type": "income", "icon": "briefcase", "color": "#10b981"},
    {"name": "Freelance", "type": "income", "icon": "laptop", "color": "#06b6d4"},
    {"name": "Business", "type": "income", "icon": "building", "color": "#3b82f6"},
    {
        "name": "Investments / Interest",
        "type": "income",
        "icon": "trending-up",
        "color": "#6366f1",
    },
    {
        "name": "Cashback & Rewards",
        "type": "income",
        "icon": "gift",
        "color": "#8b5cf6",
    },
    {"name": "Other Income", "type": "income", "icon": "plus-circle", "color": "#6b7280"},
    # Expenses
    {
        "name": "Food & Dining",
        "type": "expense",
        "icon": "utensils",
        "color": "#f97316",
    },
    {
        "name": "Groceries",
        "type": "expense",
        "icon": "shopping-cart",
        "color": "#84cc16",
    },
    {
        "name": "Transportation",
        "type": "expense",
        "icon": "car",
        "color": "#eab308",
    },
    {"name": "Shopping", "type": "expense", "icon": "shopping-bag", "color": "#ec4899"},
    {"name": "Housing & Rent", "type": "expense", "icon": "home", "color": "#f43f5e"},
    {
        "name": "Utilities & Bills",
        "type": "expense",
        "icon": "zap",
        "color": "#eab308",
    },
    {"name": "Healthcare", "type": "expense", "icon": "activity", "color": "#ef4444"},
    {"name": "Education", "type": "expense", "icon": "book-open", "color": "#06b6d4"},
    {
        "name": "Entertainment",
        "type": "expense",
        "icon": "film",
        "color": "#a855f7",
    },
    {"name": "Travel", "type": "expense", "icon": "plane", "color": "#0ea5e9"},
    {"name": "Insurance", "type": "expense", "icon": "shield", "color": "#3b82f6"},
    {
        "name": "Subscriptions",
        "type": "expense",
        "icon": "credit-card",
        "color": "#8b5cf6",
    },
    {
        "name": "Loan Interest",
        "type": "expense",
        "icon": "percent",
        "color": "#f43f5e",
    },
    {
        "name": "Other Expenses",
        "type": "expense",
        "icon": "minus-circle",
        "color": "#64748b",
    },
]


class CategoryService:
    """Service managing financial categories with idempotent system seeding."""

    def __init__(self):
        self.category_repo = CategoryRepository()

    def seed_default_categories(self, db: Session, commit: bool = True) -> None:
        """Seeds standard Indian transaction categories if not already present."""
        created_any = False
        try:
            for item in SYSTEM_CATEGORIES:
                existing = self.category_repo.get_system_category_by_name(
                    db, item["name"], item["type"]
                )
                if not existing:
                    cat = FinancialCategory(
                        user_id=None,
                        name=item["name"],
                        category_type=item["type"],
                        icon=item["icon"],
                        color=item["color"],
                        is_system=True,
                    )
                    self.category_repo.create(db, cat)
                    created_any = True
            if created_any and commit:
                db.commit()
        except Exception:
            if commit:
                db.rollback()
            raise

    def list_categories(
        self, db: Session, user: User, category_type: str | None = None
    ) -> list[CategoryResponse]:
        self.seed_default_categories(db)
        cats = self.category_repo.list_accessible_categories(db, user.id, category_type)
        return [CategoryResponse.model_validate(c) for c in cats]

    def create_custom_category(
        self, db: Session, user: User, req: CategoryCreateRequest
    ) -> CategoryResponse:
        existing = self.category_repo.get_user_category_by_name(
            db, user.id, req.name, req.category_type
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Category '{req.name}' already exists for type '{req.category_type}'.",
            )
        try:
            cat = FinancialCategory(
                user_id=user.id,
                name=req.name.strip(),
                category_type=req.category_type,
                icon=req.icon,
                color=req.color,
                is_system=False,
            )
            self.category_repo.create(db, cat)
            db.commit()
            db.refresh(cat)
            return CategoryResponse.model_validate(cat)
        except Exception:
            db.rollback()
            raise

    def update_custom_category(
        self,
        db: Session,
        user: User,
        category_id: uuid.UUID,
        req: CategoryUpdateRequest,
    ) -> CategoryResponse:
        cat = self.category_repo.get_by_id(db, category_id, user.id)
        if not cat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found.",
            )
        if cat.is_system or cat.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Default system categories cannot be modified.",
            )
        try:
            if req.name:
                cat.name = req.name.strip()
            if req.icon is not None:
                cat.icon = req.icon
            if req.color is not None:
                cat.color = req.color
            self.category_repo.update(db, cat)
            db.commit()
            db.refresh(cat)
            return CategoryResponse.model_validate(cat)
        except Exception:
            db.rollback()
            raise

    def delete_custom_category(self, db: Session, user: User, category_id: uuid.UUID) -> None:
        cat = self.category_repo.get_by_id(db, category_id, user.id)
        if not cat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found.",
            )
        if cat.is_system or cat.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Default system categories cannot be deleted.",
            )
        if cat.transactions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete category that is referenced by existing transactions.",
            )
        try:
            self.category_repo.delete(db, cat)
            db.commit()
        except Exception:
            db.rollback()
            raise
