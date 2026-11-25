import datetime as dt
import uuid

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, verify_csrf
from app.core.config import settings
from app.core.rate_limit import rate_limiter
from app.models.user import User
from app.schemas.documents import (
    DocumentConfirmRequest,
    DocumentExtractionResponse,
    DocumentExtractionUpdateRequest,
    DocumentLinkRequest,
    DocumentListResponse,
    DocumentOverviewResponse,
    DocumentProcessingHistoryResponse,
    DocumentProcessingJobResponse,
    DocumentRejectRequest,
    FinancialDocumentDetailResponse,
)
from app.services.documents.document_service import DocumentService
from app.services.documents.worker import document_ocr_worker

router = APIRouter(prefix="/documents", tags=["Documents & OCR"])
doc_service = DocumentService()


def _enforce_doc_rate_limit(user_id: uuid.UUID, op: str) -> None:
    allowed = rate_limiter.is_allowed(
        f"doc:{op}:{user_id}",
        max_requests=settings.DOCUMENT_UPLOAD_RATE_LIMIT_MAX,
        window_seconds=60,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Document {op} rate limit exceeded. Please wait a minute and retry.",
        )


@router.post(
    "/upload",
    response_model=FinancialDocumentDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a private financial document (PDF, JPG, JPEG, PNG, WebP) and queue OCR",
)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    document_category: str = Form("other"),
    auto_process: bool = Form(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    _enforce_doc_rate_limit(current_user.id, "upload")
    cap = settings.DOCUMENT_MAX_FILE_SIZE_BYTES
    data = await file.read(cap + 1)
    if len(data) > cap:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Document exceeds maximum allowed size of {cap // (1024 * 1024)} MB.",
        )
    detail, job_id = doc_service.upload_document(
        db,
        current_user,
        filename=file.filename,
        file_bytes=data,
        document_category=document_category,
        enqueue_ocr=auto_process,
    )
    if job_id is not None and settings.ENVIRONMENT.lower() != "test":
        background_tasks.add_task(document_ocr_worker.process_document_job_by_id, job_id)
    return detail


@router.get("/overview", response_model=DocumentOverviewResponse)
def get_documents_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return doc_service.get_overview(db, current_user)


@router.get("/processing-history", response_model=DocumentProcessingHistoryResponse)
def list_processing_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return doc_service.list_processing_history(db, current_user)


@router.get("", response_model=DocumentListResponse)
def list_documents(
    category: str | None = Query(None),
    status_filter: str | None = Query(None),
    ocr_status: str | None = Query(None),
    source: str | None = Query(None),
    search: str | None = Query(None),
    date_from: dt.date | None = Query(None),
    date_to: dt.date | None = Query(None),
    linked_target_type: str | None = Query(None),
    linked_target_id: uuid.UUID | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return doc_service.list_documents(
        db,
        current_user,
        category=category,
        status_filter=status_filter,
        ocr_status=ocr_status,
        source=source,
        search=search,
        date_from=date_from,
        date_to=date_to,
        linked_target_type=linked_target_type,
        linked_target_id=linked_target_id,
        page=page,
        page_size=page_size,
    )


@router.get("/{document_id}", response_model=FinancialDocumentDetailResponse)
def get_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return doc_service.get_document(db, current_user, document_id)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    doc_service.delete_document(db, current_user, document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{document_id}/download")
def download_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc, payload = doc_service.get_download_payload(db, current_user, document_id)
    safe_name = doc.original_filename.replace('"', "")
    return Response(
        content=payload,
        media_type=doc.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/{document_id}/preview")
def preview_document(
    document_id: uuid.UUID,
    page: int = Query(1, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    png_bytes, total_pages = doc_service.get_preview_png(db, current_user, document_id, page=page)
    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={
            "X-Total-Pages": str(total_pages),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.post("/{document_id}/process", response_model=DocumentProcessingJobResponse)
def process_document(
    document_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    _enforce_doc_rate_limit(current_user.id, "process")
    job_resp, queued_id = doc_service.enqueue_processing(db, current_user, document_id)
    if queued_id is not None and settings.ENVIRONMENT.lower() != "test":
        background_tasks.add_task(document_ocr_worker.process_document_job_by_id, queued_id)
    return job_resp


@router.get("/{document_id}/processing-status")
def get_processing_status(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return doc_service.get_processing_status(db, current_user, document_id)


@router.get("/{document_id}/extraction", response_model=DocumentExtractionResponse)
def get_document_extraction(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return doc_service.get_extraction(db, current_user, document_id)


@router.patch("/{document_id}/extraction", response_model=FinancialDocumentDetailResponse)
def update_document_extraction(
    document_id: uuid.UUID,
    req: DocumentExtractionUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    return doc_service.update_extraction(db, current_user, document_id, req)


@router.post("/{document_id}/confirm", response_model=FinancialDocumentDetailResponse)
def confirm_document(
    document_id: uuid.UUID,
    req: DocumentConfirmRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    return doc_service.confirm_document(db, current_user, document_id, req)


@router.post("/{document_id}/reject", response_model=FinancialDocumentDetailResponse)
def reject_document(
    document_id: uuid.UUID,
    req: DocumentRejectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    return doc_service.reject_document(db, current_user, document_id, req)


@router.post("/{document_id}/link", response_model=FinancialDocumentDetailResponse)
def link_document(
    document_id: uuid.UUID,
    req: DocumentLinkRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    return doc_service.link_document(db, current_user, document_id, req)
