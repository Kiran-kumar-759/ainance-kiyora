import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, verify_csrf
from app.models.user import User
from app.schemas.bills import NotificationListResponse, NotificationResponse
from app.services.bills.bill_service import BillService

router = APIRouter(prefix="/notifications", tags=["Notifications"])
bill_service = BillService()


@router.get("", response_model=NotificationListResponse, summary="List user in-app notifications")
def list_notifications(
    unread_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return bill_service.list_notifications(db, current_user, unread_only=unread_only)


@router.get("/unread-count", summary="Get unread notifications count")
def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    res = bill_service.list_notifications(db, current_user, unread_only=True)
    return {"unread_count": res.unread_count}


@router.post("/read-all", summary="Mark all unread notifications as read")
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    return bill_service.mark_all_notifications_read(db, current_user)


@router.patch(
    "/{notification_id}/read",
    response_model=NotificationResponse,
    summary="Mark one notification as read",
)
def mark_notification_read(
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    return bill_service.mark_notification_read(db, current_user, notification_id)
