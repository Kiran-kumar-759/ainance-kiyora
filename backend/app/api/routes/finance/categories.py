import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, verify_csrf
from app.models.user import User
from app.schemas.finance.category import (
    CategoryCreateRequest,
    CategoryResponse,
    CategoryUpdateRequest,
)
from app.services.finance.category_service import CategoryService

router = APIRouter(prefix="/finance/categories", tags=["Transaction Categories"])
category_service = CategoryService()


@router.get("", response_model=list[CategoryResponse], summary="List transaction categories")
def list_categories(
    category_type: str | None = Query(None, description="Filter by type: income or expense"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns all system and user custom transaction categories."""
    return category_service.list_categories(db, current_user, category_type=category_type)


@router.post("", response_model=CategoryResponse, summary="Create a custom category")
def create_category(
    req: CategoryCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    """Creates a user-owned custom transaction category."""
    return category_service.create_custom_category(db, current_user, req)


@router.patch("/{category_id}", response_model=CategoryResponse, summary="Update custom category")
def update_category(
    category_id: uuid.UUID,
    req: CategoryUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    """Updates a user custom category (system categories cannot be edited)."""
    return category_service.update_custom_category(db, current_user, category_id, req)


@router.delete(
    "/{category_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete custom category"
)
def delete_category(
    category_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    """Deletes an unused custom category (system categories or in-use categories cannot be deleted)."""
    category_service.delete_custom_category(db, current_user, category_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
