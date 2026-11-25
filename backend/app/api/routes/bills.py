import datetime as dt
import uuid

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, verify_csrf
from app.core.config import settings
from app.models.user import User
from app.schemas.bills import (
    BillCreateRequest,
    BillDocumentResponse,
    BillListResponse,
    BillPaymentCreateRequest,
    BillPaymentLinkTransactionRequest,
    BillPaymentListResponse,
    BillReminderUpdateRequest,
    BillResponse,
    BillsOverviewResponse,
    BillUpdateRequest,
    GenerateOccurrenceResponse,
    ProcessRemindersResponse,
    RecurrenceScheduleResponse,
    RecurrenceScheduleUpdateRequest,
)
from app.services.bills.bill_service import BillService
from app.services.bills.reminder_service import ReminderService

router = APIRouter(prefix="/bills", tags=["Bills & Payments"])
bill_service = BillService()
reminder_service = ReminderService()


@router.post(
    "",
    response_model=BillResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a one-time or recurring bill",
)
def create_bill(
    req: BillCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    return bill_service.create_bill(db, current_user, req)


@router.get("", response_model=BillListResponse, summary="List bills with filters and pagination")
def list_bills(
    status_filter: str | None = Query(
        None, description="upcoming, due_soon, overdue, paid, archived"
    ),
    bill_category: str | None = Query(None),
    bill_type: str | None = Query(None, description="one_time or recurring"),
    start_date: dt.date | None = Query(None),
    end_date: dt.date | None = Query(None),
    search: str | None = Query(None),
    sort_by: str = Query(
        "due_date_asc",
        description="due_date_asc, due_date_desc, amount_desc, amount_asc, name_asc",
    ),
    include_archived: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return bill_service.list_bills(
        db=db,
        user=current_user,
        status_filter=status_filter,
        bill_category=bill_category,
        bill_type=bill_type,
        start_date=start_date,
        end_date=end_date,
        search=search,
        sort_by=sort_by,
        include_archived=include_archived,
        page=page,
        page_size=page_size,
    )


@router.get("/overview", response_model=BillsOverviewResponse, summary="Get bills overview summary")
def get_bills_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return bill_service.get_bills_overview(db, current_user)


@router.get("/upcoming", response_model=BillListResponse, summary="List upcoming and due-soon bills")
def list_upcoming_bills(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    res = bill_service.list_bills(db, current_user, page=1, page_size=500)
    filtered = [b for b in res.items if b.derived_status in {"upcoming", "due_soon"}]
    total = len(filtered)
    start = (page - 1) * page_size
    return BillListResponse(
        items=filtered[start : start + page_size],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=max(1, (total + page_size - 1) // page_size),
    )


@router.get("/overdue", response_model=BillListResponse, summary="List overdue bills")
def list_overdue_bills(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return bill_service.list_bills(
        db, current_user, status_filter="overdue", page=page, page_size=page_size
    )


@router.get("/paid", response_model=BillListResponse, summary="List paid bills")
def list_paid_bills(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return bill_service.list_bills(
        db, current_user, status_filter="paid", sort_by="due_date_desc", page=page, page_size=page_size
    )


@router.get("/payments", response_model=BillPaymentListResponse, summary="List all bill payment history")
def list_all_bill_payments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return bill_service.list_payment_history(db, current_user)


@router.get("/schedules", response_model=list[RecurrenceScheduleResponse], summary="List recurring bill schedules")
def list_recurrence_schedules(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return bill_service.list_schedules(db, current_user)


@router.patch(
    "/schedules/{schedule_id}",
    response_model=RecurrenceScheduleResponse,
    summary="Update a recurring bill schedule",
)
def update_recurrence_schedule(
    schedule_id: uuid.UUID,
    req: RecurrenceScheduleUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    return bill_service.update_schedule(db, current_user, schedule_id, req)


@router.post(
    "/schedules/{schedule_id}/generate-next",
    response_model=GenerateOccurrenceResponse,
    summary="Idempotently generate next unpaid recurring bill occurrence",
)
def generate_next_occurrence(
    schedule_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    return bill_service.generate_next_occurrence_for_schedule(db, current_user, schedule_id)


@router.post(
    "/reminders/process",
    response_model=ProcessRemindersResponse,
    summary="Evaluate and dispatch due reminders for the authenticated user",
)
def process_user_reminders(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    return reminder_service.process_due_reminders(db, user_id=current_user.id)


@router.get("/{bill_id}", response_model=BillResponse, summary="Get bill details")
def get_bill(
    bill_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return bill_service.get_bill(db, current_user, bill_id)


@router.patch("/{bill_id}", response_model=BillResponse, summary="Update bill details")
def update_bill(
    bill_id: uuid.UUID,
    req: BillUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    return bill_service.update_bill(db, current_user, bill_id, req)


@router.post("/{bill_id}/archive", response_model=BillResponse, summary="Archive bill")
def archive_bill(
    bill_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    return bill_service.archive_bill(db, current_user, bill_id)


@router.post(
    "/{bill_id}/payments",
    response_model=BillResponse,
    summary="Record a bill payment and post atomic ledger transaction",
)
def record_bill_payment(
    bill_id: uuid.UUID,
    req: BillPaymentCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    return bill_service.record_payment(db, current_user, bill_id, req)


@router.post(
    "/{bill_id}/payments/link-transaction",
    response_model=BillResponse,
    summary="Link an existing financial transaction to settle a bill",
)
def link_transaction_to_bill(
    bill_id: uuid.UUID,
    req: BillPaymentLinkTransactionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    return bill_service.link_existing_transaction(db, current_user, bill_id, req)


@router.get(
    "/{bill_id}/payments",
    response_model=BillPaymentListResponse,
    summary="Get payment history for a specific bill",
)
def get_bill_payments(
    bill_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return bill_service.list_payment_history(db, current_user, bill_id=bill_id)


@router.put(
    "/{bill_id}/reminders",
    response_model=BillResponse,
    summary="Update bill reminder preferences and channels",
)
def update_bill_reminders(
    bill_id: uuid.UUID,
    req: BillReminderUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    return bill_service.update_bill_reminders(db, current_user, bill_id, req)


@router.post(
    "/{bill_id}/documents",
    response_model=BillDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload supporting bill document",
)
async def upload_bill_document(
    bill_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    cap = settings.BILL_MAX_DOC_SIZE_BYTES
    data = await file.read(cap + 1)
    if len(data) > cap:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Document exceeds maximum allowed size of {cap // (1024 * 1024)} MB.",
        )
    return bill_service.upload_document(db, current_user, bill_id, file.filename, data)


@router.get(
    "/{bill_id}/documents/{doc_id}/download",
    summary="Privately download supporting bill document",
)
def download_bill_document(
    bill_id: uuid.UUID,
    doc_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc, data = bill_service.download_document(db, current_user, bill_id, doc_id)
    return Response(
        content=data,
        media_type=doc.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{doc.original_filename}"',
            "X-Content-Type-Options": "nosniff",
        },
    )
