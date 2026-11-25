import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, verify_csrf
from app.core.config import settings
from app.models.user import User
from app.schemas.imports import (
    ImportBatchResponse,
    ImportBulkSelectRequest,
    ImportCenterOverviewResponse,
    ImportColumnsResponse,
    ImportCommitResponse,
    ImportDuplicateReviewRequest,
    ImportMappingConfig,
    ImportMappingProfileResponse,
    ImportPreviewResponse,
    ImportRowListResponse,
    ImportRowResponse,
    ImportRowUpdateRequest,
    ImportSummaryResponse,
)
from app.services.imports.import_service import ImportService

router = APIRouter(prefix="/imports", tags=["Bank Statement Imports"])
import_service = ImportService()


@router.post(
    "/upload",
    response_model=ImportPreviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload CSV or XLSX bank statement",
)
async def upload_statement(
    account_id: uuid.UUID = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    """
    Uploads and privately stores a CSV or XLSX bank statement for the specified account,
    inspects structure, and returns preview & candidate column mapping suggestions.
    """
    max_allowed = settings.IMPORT_MAX_FILE_SIZE_BYTES
    data = await file.read(max_allowed + 1)
    if len(data) > max_allowed:
        max_mb = round(max_allowed / (1024 * 1024), 1)
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of {max_mb} MB.",
        )

    return import_service.upload_statement(
        db=db,
        user=current_user,
        account_id=account_id,
        filename=file.filename,
        file_bytes=data,
    )


@router.get("", response_model=ImportCenterOverviewResponse, summary="List user statement imports")
def list_imports(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns import center summary metrics and import history for the authenticated user."""
    return import_service.list_batches(db, current_user)


@router.get(
    "/profiles",
    response_model=list[ImportMappingProfileResponse],
    summary="List saved column mapping profiles",
)
def list_mapping_profiles(
    file_format: str | None = Query(None, description="Optional filter: csv or xlsx"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns saved column mapping profiles owned by the authenticated user."""
    return import_service.list_mapping_profiles(db, current_user, file_format=file_format)


@router.get("/{import_id}", response_model=ImportBatchResponse, summary="Get import batch details")
def get_import(
    import_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieves full metadata and lifecycle history for an import batch."""
    return import_service.get_batch(db, current_user, import_id)


@router.get(
    "/{import_id}/preview",
    response_model=ImportPreviewResponse,
    summary="Preview uploaded statement sheets and sample rows",
)
def preview_import(
    import_id: uuid.UUID,
    sheet_name: str | None = Query(None),
    header_row_index: int | None = Query(None, ge=0, le=50),
    delimiter: str | None = Query(None, max_length=3),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Previews uploaded CSV or XLSX contents and optionally switches sheet/header row."""
    return import_service.get_preview(
        db=db,
        user=current_user,
        batch_id=import_id,
        sheet_name=sheet_name,
        header_row_index=header_row_index,
        delimiter=delimiter,
    )


@router.delete("/{import_id}", summary="Cancel and delete an unimported statement batch")
def delete_import(
    import_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    """Deletes an unimported/cancelled batch and securely removes its stored file."""
    return import_service.delete_or_cancel_batch(db, current_user, import_id)


@router.get(
    "/{import_id}/columns",
    response_model=ImportColumnsResponse,
    summary="Inspect detected columns and mapping options",
)
def get_import_columns(
    import_id: uuid.UUID,
    sheet_name: str | None = Query(None),
    header_row_index: int | None = Query(None, ge=0, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns detected columns, sample rows, candidate mapping, and user saved profiles."""
    return import_service.get_columns(
        db=db,
        user=current_user,
        batch_id=import_id,
        sheet_name=sheet_name,
        header_row_index=header_row_index,
    )


@router.put(
    "/{import_id}/mapping",
    response_model=ImportBatchResponse,
    summary="Confirm column mapping and validate statement rows",
)
def save_import_mapping(
    import_id: uuid.UUID,
    req: ImportMappingConfig,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    """Saves confirmed column mapping, parses rows, validates data, and runs duplicate detection."""
    return import_service.apply_mapping_and_validate(db, current_user, import_id, req)


@router.post(
    "/{import_id}/validate",
    response_model=ImportBatchResponse,
    summary="Re-run deterministic validation and duplicate checks",
)
def validate_import(
    import_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    """Re-validates all statement rows against the saved mapping configuration."""
    return import_service.validate_batch(db, current_user, import_id)


@router.get(
    "/{import_id}/rows",
    response_model=ImportRowListResponse,
    summary="List normalized statement rows for review",
)
def list_import_rows(
    import_id: uuid.UUID,
    status_filter: str | None = Query(None, description="valid, invalid, needs_review, duplicate, potential_duplicate, excluded, imported"),
    duplicate_only: bool = Query(False),
    search: str | None = Query(None),
    sort_by: str = Query("row_asc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns paginated parsed rows with validation statuses, duplicate flags, and category assignments."""
    return import_service.list_rows(
        db=db,
        user=current_user,
        batch_id=import_id,
        status_filter=status_filter,
        duplicate_only=duplicate_only,
        search=search,
        sort_by=sort_by,
        page=page,
        page_size=page_size,
    )


@router.patch(
    "/{import_id}/rows/bulk-select",
    response_model=ImportBatchResponse,
    summary="Bulk select or deselect valid statement rows",
)
def bulk_select_import_rows(
    import_id: uuid.UUID,
    req: ImportBulkSelectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    """Bulk updates row selection states cleanly."""
    return import_service.bulk_select_rows(db, current_user, import_id, req)


@router.patch(
    "/{import_id}/rows/{row_id}",
    response_model=ImportRowResponse,
    summary="Edit, categorize, select, or exclude an individual import row",
)
def update_import_row(
    import_id: uuid.UUID,
    row_id: uuid.UUID,
    req: ImportRowUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    """Allows reviewing and editing individual statement rows prior to committing."""
    return import_service.update_row(db, current_user, import_id, row_id, req)


@router.get(
    "/{import_id}/duplicates",
    response_model=ImportRowListResponse,
    summary="List duplicate and potential duplicate rows",
)
def list_import_duplicates(
    import_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns all flagged duplicate and potential duplicate rows in the import batch."""
    return import_service.list_duplicates(db, current_user, import_id, page=page, page_size=page_size)


@router.patch(
    "/{import_id}/rows/{row_id}/duplicate-review",
    response_model=ImportRowResponse,
    summary="Resolve a potential duplicate row decision",
)
def review_import_duplicate(
    import_id: uuid.UUID,
    row_id: uuid.UUID,
    req: ImportDuplicateReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    """Marks a potential duplicate row to be imported as legitimate or skipped cleanly."""
    return import_service.review_duplicate(db, current_user, import_id, row_id, req)


@router.post(
    "/{import_id}/commit",
    response_model=ImportCommitResponse,
    summary="Commit selected transactions into financial ledger",
)
def commit_import(
    import_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    """
    Atomically imports all selected valid transactions through TransactionService and LedgerService,
    preserving double-entry integrity and recalculating account balance.
    """
    return import_service.commit_import(db, current_user, import_id)


@router.get(
    "/{import_id}/summary",
    response_model=ImportSummaryResponse,
    summary="Get pre-commit or post-commit import summary",
)
def get_import_summary(
    import_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns exact Decimal income, expense, net totals, and row breakdown counts."""
    return import_service.get_summary(db, current_user, import_id)
