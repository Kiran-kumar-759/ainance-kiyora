import datetime as dt
import uuid
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.imports import ImportBatch, ImportRow
from app.models.user import User
from app.repositories.finance.account_repository import AccountRepository
from app.repositories.finance.category_repository import CategoryRepository
from app.repositories.finance.import_repository import ImportRepository
from app.schemas.finance.transaction import TransactionCreateRequest
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
from app.services.finance.category_service import CategoryService
from app.services.finance.transaction_service import TransactionService
from app.services.imports.duplicate_detector import detect_duplicates_for_batch
from app.services.imports.normalizer import compute_row_fingerprint, normalize_row
from app.services.imports.parsers import inspect_statement_bytes, validate_upload_content
from app.services.imports.storage import LocalPrivateFileStorage

ALLOWED_STATE_TRANSITIONS: dict[str, set[str]] = {
    "uploaded": {"parsing", "mapping_required", "failed", "cancelled"},
    "parsing": {"mapping_required", "failed", "cancelled"},
    "mapping_required": {"mapping_required", "validating", "ready_for_review", "failed", "cancelled"},
    "validating": {"ready_for_review", "failed", "cancelled"},
    "ready_for_review": {
        "mapping_required",
        "validating",
        "ready_for_review",
        "importing",
        "cancelled",
    },
    "importing": {"completed", "completed_with_errors", "failed"},
    "completed": set(),
    "completed_with_errors": set(),
    "failed": {"cancelled"},
    "cancelled": set(),
}


class ImportService:
    """
    Orchestrates secure bank statement uploads, CSV/XLSX inspection, column mapping,
    deterministic normalization/validation, 3-layer duplicate detection, and atomic
    double-entry financial persistence through TransactionService.
    """

    def __init__(self, storage: LocalPrivateFileStorage | None = None):
        self.import_repo = ImportRepository()
        self.account_repo = AccountRepository()
        self.category_repo = CategoryRepository()
        self.category_service = CategoryService()
        self.transaction_service = TransactionService()
        self.storage = storage or LocalPrivateFileStorage()

    def _batch_to_response(self, batch: ImportBatch) -> ImportBatchResponse:
        return ImportBatchResponse(
            id=batch.id,
            user_id=batch.user_id,
            account_id=batch.account_id,
            account_name=batch.account.name if batch.account else None,
            account_type=batch.account.account_type if batch.account else None,
            original_filename=batch.original_filename,
            file_hash=batch.file_hash,
            file_size=batch.file_size,
            file_type=batch.file_type,
            status=batch.status,
            sheet_name=batch.sheet_name,
            header_row_index=batch.header_row_index,
            delimiter=batch.delimiter,
            total_rows=batch.total_rows,
            valid_rows=batch.valid_rows,
            invalid_rows=batch.invalid_rows,
            needs_review_rows=batch.needs_review_rows,
            duplicate_rows=batch.duplicate_rows,
            potential_duplicate_rows=batch.potential_duplicate_rows,
            imported_rows=batch.imported_rows,
            skipped_rows=batch.skipped_rows,
            total_income=batch.total_income,
            total_expenses=batch.total_expenses,
            mapping_configuration=batch.mapping_configuration,
            lifecycle_history=batch.lifecycle_history or [],
            failure_reason=batch.failure_reason,
            created_at=batch.created_at,
            updated_at=batch.updated_at,
            completed_at=batch.completed_at,
        )

    def _row_to_response(self, row: ImportRow) -> ImportRowResponse:
        return ImportRowResponse(
            id=row.id,
            import_batch_id=row.import_batch_id,
            source_row_number=row.source_row_number,
            raw_row_data=row.raw_row_data,
            normalized_date=row.normalized_date,
            normalized_description=row.normalized_description,
            normalized_merchant=row.normalized_merchant,
            normalized_notes=row.normalized_notes,
            normalized_amount=row.normalized_amount,
            normalized_type=row.normalized_type,
            currency=row.currency,
            transaction_reference=row.transaction_reference,
            running_balance=row.running_balance,
            row_fingerprint=row.row_fingerprint,
            validation_status=row.validation_status,
            duplicate_status=row.duplicate_status,
            duplicate_match_transaction_id=row.duplicate_match_transaction_id,
            duplicate_match_row_id=row.duplicate_match_row_id,
            validation_errors=row.validation_errors or [],
            category_id=row.category_id,
            category_name=row.category.name if row.category else None,
            is_selected=row.is_selected,
            review_changes=row.review_changes,
            imported_transaction_id=row.imported_transaction_id,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _transition_state(self, batch: ImportBatch, target_state: str, note: str = "") -> None:
        current = batch.status
        allowed = ALLOWED_STATE_TRANSITIONS.get(current, set())
        if target_state not in allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid import state transition from '{current}' to '{target_state}'.",
            )
        history = list(batch.lifecycle_history or [])
        history.append(
            {
                "from": current,
                "to": target_state,
                "at": dt.datetime.now(dt.UTC).isoformat(),
                "note": note,
            }
        )
        batch.lifecycle_history = history
        batch.status = target_state

    def _recompute_batch_counts(self, batch: ImportBatch, rows: list[ImportRow]) -> None:
        batch.total_rows = len(rows)
        batch.valid_rows = sum(1 for r in rows if r.validation_status == "valid")
        batch.invalid_rows = sum(1 for r in rows if r.validation_status == "invalid")
        batch.needs_review_rows = sum(1 for r in rows if r.validation_status == "needs_review")
        batch.duplicate_rows = sum(1 for r in rows if r.validation_status == "duplicate")
        batch.potential_duplicate_rows = sum(
            1 for r in rows if r.validation_status == "potential_duplicate"
        )
        batch.imported_rows = sum(1 for r in rows if r.validation_status == "imported")
        batch.skipped_rows = sum(
            1 for r in rows if r.validation_status in {"excluded", "invalid", "duplicate"}
        )

    def _get_owned_batch(self, db: Session, user: User, batch_id: uuid.UUID) -> ImportBatch:
        batch = self.import_repo.get_batch(db, batch_id, user.id)
        if not batch:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Import batch not found.",
            )
        return batch

    def upload_statement(
        self,
        db: Session,
        user: User,
        account_id: uuid.UUID,
        filename: str | None,
        file_bytes: bytes,
    ) -> ImportPreviewResponse:
        account = self.account_repo.get_by_id(db, account_id, user.id)
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Destination financial account not found.",
            )
        if account.status != "active":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot import statements into an archived account.",
            )

        try:
            safe_name, file_type, file_hash = validate_upload_content(
                filename=filename,
                data=file_bytes,
                max_size_bytes=settings.IMPORT_MAX_FILE_SIZE_BYTES,
            )
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(err),
            ) from err

        try:
            inspection = inspect_statement_bytes(
                data=file_bytes,
                file_type=file_type,
                max_rows=settings.IMPORT_MAX_ROWS_PER_FILE,
            )
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(err),
            ) from err

        from sqlalchemy import select as sa_select

        prior_same_file = db.execute(
            sa_select(ImportBatch.id).where(
                ImportBatch.user_id == user.id,
                ImportBatch.account_id == account.id,
                ImportBatch.file_hash == file_hash,
                ImportBatch.status.in_(["completed", "completed_with_errors"]),
            )
        ).first()
        upload_note = f"Uploaded {safe_name} ({file_type.upper()}, {len(file_bytes)} bytes)"
        if prior_same_file is not None:
            upload_note += " — Identical file was previously imported into this account."

        batch_id = uuid.uuid4()
        storage_key: str | None = None
        try:
            storage_key = self.storage.save(user.id, batch_id, file_type, file_bytes)
            batch = ImportBatch(
                id=batch_id,
                user_id=user.id,
                account_id=account.id,
                original_filename=safe_name,
                file_hash=file_hash,
                file_size=len(file_bytes),
                file_type=file_type,
                storage_key=storage_key,
                status="uploaded",
                sheet_name=inspection.selected_sheet,
                header_row_index=inspection.header_row_index,
                delimiter=inspection.delimiter,
                total_rows=inspection.total_raw_rows,
                mapping_configuration=inspection.suggested_mapping,
                inspection_metadata={
                    "available_sheets": inspection.available_sheets,
                    "selected_sheet": inspection.selected_sheet,
                    "columns": inspection.columns,
                    "preview_rows": inspection.preview_rows,
                    "sample_mapped_rows": inspection.sample_mapped_rows,
                    "suggested_mapping": inspection.suggested_mapping,
                    "reupload_detected": prior_same_file is not None,
                },
                lifecycle_history=[
                    {
                        "from": None,
                        "to": "uploaded",
                        "at": dt.datetime.now(dt.UTC).isoformat(),
                        "note": upload_note,
                    }
                ],
            )
            self._transition_state(
                batch,
                "mapping_required",
                f"Inspected {inspection.total_raw_rows} rows across {len(inspection.columns)} columns.",
            )
            self.import_repo.create_batch(db, batch)
            db.commit()
            batch = self._get_owned_batch(db, user, batch.id)
            return ImportPreviewResponse(
                batch=self._batch_to_response(batch),
                available_sheets=inspection.available_sheets,
                selected_sheet=inspection.selected_sheet,
                header_row_index=inspection.header_row_index,
                delimiter=inspection.delimiter,
                columns=inspection.columns,
                preview_rows=inspection.preview_rows,
                sample_mapped_rows=inspection.sample_mapped_rows,
                suggested_mapping=inspection.suggested_mapping,
            )
        except Exception:
            db.rollback()
            if storage_key:
                self.storage.delete(storage_key)
            raise

    def list_batches(self, db: Session, user: User) -> ImportCenterOverviewResponse:
        batches = self.import_repo.list_batches(db, user.id)
        responses = [self._batch_to_response(b) for b in batches]
        return ImportCenterOverviewResponse(
            total_imports=len(batches),
            completed_imports=sum(
                1 for b in batches if b.status in {"completed", "completed_with_errors"}
            ),
            failed_imports=sum(1 for b in batches if b.status == "failed"),
            transactions_imported=sum(b.imported_rows for b in batches),
            batches=responses,
        )

    def get_batch(self, db: Session, user: User, batch_id: uuid.UUID) -> ImportBatchResponse:
        batch = self._get_owned_batch(db, user, batch_id)
        return self._batch_to_response(batch)

    def _reinspect_if_requested(
        self,
        db: Session,
        batch: ImportBatch,
        sheet_name: str | None = None,
        header_row_index: int | None = None,
        delimiter: str | None = None,
    ) -> dict[str, Any]:
        meta = dict(batch.inspection_metadata or {})
        needs_reparse = (
            (sheet_name is not None and sheet_name != batch.sheet_name)
            or (header_row_index is not None and header_row_index != batch.header_row_index)
            or (delimiter is not None and delimiter != batch.delimiter)
            or not meta
        )
        if not needs_reparse:
            return meta

        if batch.status in {"completed", "completed_with_errors", "importing"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot change parsing configuration after import execution.",
            )
        if not batch.storage_key or not self.storage.exists(batch.storage_key):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Uploaded statement file is no longer available in storage.",
            )

        data = self.storage.read_bytes(batch.storage_key)
        try:
            inspection = inspect_statement_bytes(
                data=data,
                file_type=batch.file_type,
                max_rows=settings.IMPORT_MAX_ROWS_PER_FILE,
                sheet_name=sheet_name or batch.sheet_name,
                header_row_index=(
                    header_row_index if header_row_index is not None else batch.header_row_index
                ),
                delimiter=delimiter or batch.delimiter,
            )
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(err),
            ) from err

        batch.sheet_name = inspection.selected_sheet
        batch.header_row_index = inspection.header_row_index
        batch.delimiter = inspection.delimiter
        batch.total_rows = inspection.total_raw_rows
        meta = {
            "available_sheets": inspection.available_sheets,
            "selected_sheet": inspection.selected_sheet,
            "columns": inspection.columns,
            "preview_rows": inspection.preview_rows,
            "sample_mapped_rows": inspection.sample_mapped_rows,
            "suggested_mapping": inspection.suggested_mapping,
        }
        batch.inspection_metadata = meta
        self.import_repo.update_batch(db, batch)
        db.commit()
        db.refresh(batch)
        return meta

    def get_preview(
        self,
        db: Session,
        user: User,
        batch_id: uuid.UUID,
        sheet_name: str | None = None,
        header_row_index: int | None = None,
        delimiter: str | None = None,
    ) -> ImportPreviewResponse:
        batch = self._get_owned_batch(db, user, batch_id)
        meta = self._reinspect_if_requested(
            db, batch, sheet_name=sheet_name, header_row_index=header_row_index, delimiter=delimiter
        )
        return ImportPreviewResponse(
            batch=self._batch_to_response(batch),
            available_sheets=meta.get("available_sheets", [batch.sheet_name or "Sheet1"]),
            selected_sheet=meta.get("selected_sheet", batch.sheet_name or "Sheet1"),
            header_row_index=batch.header_row_index,
            delimiter=batch.delimiter,
            columns=meta.get("columns", []),
            preview_rows=meta.get("preview_rows", []),
            sample_mapped_rows=meta.get("sample_mapped_rows", []),
            suggested_mapping=meta.get("suggested_mapping", {}),
        )

    def get_columns(
        self,
        db: Session,
        user: User,
        batch_id: uuid.UUID,
        sheet_name: str | None = None,
        header_row_index: int | None = None,
    ) -> ImportColumnsResponse:
        batch = self._get_owned_batch(db, user, batch_id)
        meta = self._reinspect_if_requested(
            db, batch, sheet_name=sheet_name, header_row_index=header_row_index
        )
        profiles = self.import_repo.list_mapping_profiles(db, user.id, file_format=batch.file_type)
        return ImportColumnsResponse(
            batch_id=batch.id,
            file_type=batch.file_type,
            available_sheets=meta.get("available_sheets", [batch.sheet_name or "Sheet1"]),
            selected_sheet=meta.get("selected_sheet", batch.sheet_name or "Sheet1"),
            header_row_index=batch.header_row_index,
            columns=meta.get("columns", []),
            sample_mapped_rows=meta.get("sample_mapped_rows", []),
            suggested_mapping=meta.get("suggested_mapping", {}),
            current_mapping=batch.mapping_configuration,
            saved_profiles=[ImportMappingProfileResponse.model_validate(p) for p in profiles],
        )

    def list_mapping_profiles(
        self, db: Session, user: User, file_format: str | None = None
    ) -> list[ImportMappingProfileResponse]:
        profiles = self.import_repo.list_mapping_profiles(db, user.id, file_format=file_format)
        return [ImportMappingProfileResponse.model_validate(p) for p in profiles]

    def apply_mapping_and_validate(
        self,
        db: Session,
        user: User,
        batch_id: uuid.UUID,
        mapping: ImportMappingConfig,
    ) -> ImportBatchResponse:
        batch = self._get_owned_batch(db, user, batch_id)
        if batch.status not in {"mapping_required", "ready_for_review", "uploaded"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot modify column mapping when import batch is in '{batch.status}' state.",
            )
        if not batch.storage_key or not self.storage.exists(batch.storage_key):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Uploaded statement file is missing from private storage.",
            )

        try:
            data = self.storage.read_bytes(batch.storage_key)
            inspection = inspect_statement_bytes(
                data=data,
                file_type=batch.file_type,
                max_rows=settings.IMPORT_MAX_ROWS_PER_FILE,
                sheet_name=mapping.sheet_name or batch.sheet_name,
                header_row_index=(
                    mapping.header_row_index
                    if mapping.header_row_index is not None
                    else batch.header_row_index
                ),
                delimiter=mapping.delimiter or batch.delimiter,
            )
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(err),
            ) from err

        # Verify all mapped columns exist in inspected file columns
        col_set = set(inspection.columns)
        for col_field in (
            mapping.date_column,
            mapping.description_column,
            mapping.amount_column,
            mapping.debit_column,
            mapping.credit_column,
            mapping.type_column,
            mapping.reference_column,
            mapping.balance_column,
            mapping.merchant_column,
            mapping.notes_column,
            mapping.currency_column,
        ):
            if col_field and col_field not in col_set:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Mapped column '{col_field}' was not found in the statement headers.",
                )

        mapping_dict = mapping.model_dump(exclude={"save_profile_name"})

        try:
            batch.sheet_name = inspection.selected_sheet
            batch.header_row_index = inspection.header_row_index
            batch.delimiter = inspection.delimiter
            batch.mapping_configuration = mapping_dict
            batch.inspection_metadata = {
                "available_sheets": inspection.available_sheets,
                "selected_sheet": inspection.selected_sheet,
                "columns": inspection.columns,
                "preview_rows": inspection.preview_rows,
                "sample_mapped_rows": inspection.sample_mapped_rows,
                "suggested_mapping": inspection.suggested_mapping,
            }

            if mapping.save_profile_name and mapping.save_profile_name.strip():
                self.import_repo.upsert_mapping_profile(
                    db=db,
                    user_id=user.id,
                    profile_name=mapping.save_profile_name.strip(),
                    file_format=batch.file_type,
                    mapping_configuration=mapping_dict,
                )

            self._transition_state(batch, "validating", "Normalizing and validating rows.")

            import_rows: list[ImportRow] = []
            for raw_row in inspection.all_rows:
                source_num = int(raw_row.get("__source_row_number__", len(import_rows) + 1))
                clean_raw = {k: v for k, v in raw_row.items() if k != "__source_row_number__"}
                norm = normalize_row(clean_raw, mapping_dict)
                import_rows.append(
                    ImportRow(
                        id=uuid.uuid4(),
                        import_batch_id=batch.id,
                        source_row_number=source_num,
                        raw_row_data=clean_raw,
                        normalized_date=norm.normalized_date,
                        normalized_description=norm.normalized_description,
                        normalized_merchant=norm.normalized_merchant,
                        normalized_notes=norm.normalized_notes,
                        normalized_amount=norm.normalized_amount,
                        normalized_type=norm.normalized_type,
                        currency=norm.currency,
                        transaction_reference=norm.transaction_reference,
                        running_balance=norm.running_balance,
                        row_fingerprint=norm.row_fingerprint,
                        validation_status=norm.validation_status,
                        duplicate_status="none",
                        validation_errors=norm.validation_errors,
                        is_selected=False,
                    )
                )

            detect_duplicates_for_batch(db, batch, import_rows)
            self.import_repo.replace_rows_for_batch(db, batch.id, import_rows)
            self._recompute_batch_counts(batch, import_rows)
            self._transition_state(
                batch,
                "ready_for_review",
                f"Validated {batch.total_rows} rows ({batch.valid_rows} valid, {batch.duplicate_rows} duplicate, {batch.potential_duplicate_rows} potential duplicates, {batch.invalid_rows} invalid).",
            )
            self.import_repo.update_batch(db, batch)
            db.commit()
            return self._batch_to_response(self._get_owned_batch(db, user, batch.id))
        except Exception:
            db.rollback()
            raise

    def validate_batch(
        self, db: Session, user: User, batch_id: uuid.UUID
    ) -> ImportBatchResponse:
        batch = self._get_owned_batch(db, user, batch_id)
        if not batch.mapping_configuration:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Column mapping must be configured before validating.",
            )
        mapping = ImportMappingConfig.model_validate(batch.mapping_configuration)
        return self.apply_mapping_and_validate(db, user, batch_id, mapping)

    def list_rows(
        self,
        db: Session,
        user: User,
        batch_id: uuid.UUID,
        status_filter: str | None = None,
        duplicate_only: bool = False,
        search: str | None = None,
        sort_by: str = "row_asc",
        page: int = 1,
        page_size: int = 25,
    ) -> ImportRowListResponse:
        batch = self._get_owned_batch(db, user, batch_id)
        items, total, total_pages = self.import_repo.list_rows(
            db=db,
            batch_id=batch.id,
            status_filter=status_filter,
            duplicate_only=duplicate_only,
            search=search,
            sort_by=sort_by,
            page=page,
            page_size=page_size,
        )
        return ImportRowListResponse(
            items=[self._row_to_response(r) for r in items],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    def list_duplicates(
        self, db: Session, user: User, batch_id: uuid.UUID, page: int = 1, page_size: int = 50
    ) -> ImportRowListResponse:
        return self.list_rows(
            db=db,
            user=user,
            batch_id=batch_id,
            duplicate_only=True,
            page=page,
            page_size=page_size,
        )

    def update_row(
        self,
        db: Session,
        user: User,
        batch_id: uuid.UUID,
        row_id: uuid.UUID,
        req: ImportRowUpdateRequest,
    ) -> ImportRowResponse:
        batch = self._get_owned_batch(db, user, batch_id)
        if batch.status != "ready_for_review":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Rows cannot be edited when batch is in '{batch.status}' state.",
            )
        row = self.import_repo.get_row(db, batch.id, row_id, user.id)
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Import row not found.",
            )
        if row.validation_status == "imported" or row.imported_transaction_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Already imported rows cannot be modified.",
            )

        changes = dict(row.review_changes or {})
        try:
            if req.normalized_date is not None:
                row.normalized_date = req.normalized_date
                changes["normalized_date"] = req.normalized_date.isoformat()
            if req.normalized_description is not None:
                row.normalized_description = req.normalized_description.strip()
                changes["normalized_description"] = row.normalized_description
            if req.normalized_merchant is not None:
                row.normalized_merchant = req.normalized_merchant.strip() or None
                changes["normalized_merchant"] = row.normalized_merchant
            if req.normalized_notes is not None:
                row.normalized_notes = req.normalized_notes.strip() or None
                changes["normalized_notes"] = row.normalized_notes
            if req.normalized_amount is not None:
                row.normalized_amount = req.normalized_amount
                changes["normalized_amount"] = str(req.normalized_amount)
            if req.normalized_type is not None:
                row.normalized_type = req.normalized_type
                changes["normalized_type"] = req.normalized_type

            if req.clear_category:
                row.category_id = None
                changes["category_id"] = None
            elif req.category_id is not None:
                cat = self.category_repo.get_by_id(db, req.category_id, user.id)
                if not cat:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Selected category was not found.",
                    )
                if row.normalized_type and cat.category_type != row.normalized_type:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Category '{cat.name}' ({cat.category_type}) does not match row type '{row.normalized_type}'.",
                    )
                row.category_id = cat.id
                changes["category_id"] = str(cat.id)

            row.row_fingerprint = compute_row_fingerprint(
                row.normalized_date,
                row.normalized_amount,
                row.normalized_type,
                row.normalized_description,
            )

            if req.exclude is True:
                row.validation_status = "excluded"
                row.is_selected = False
                changes["excluded"] = True
            elif req.exclude is False or any(
                v is not None
                for v in (
                    req.normalized_date,
                    req.normalized_description,
                    req.normalized_amount,
                    req.normalized_type,
                )
            ):
                # Re-validate fields cleanly
                new_errors: list[str] = []
                if row.normalized_date is None:
                    new_errors.append("Missing transaction date.")
                if not row.normalized_description:
                    new_errors.append("Missing transaction description.")
                if row.normalized_amount is None or row.normalized_amount <= Decimal("0.00"):
                    new_errors.append("Missing or non-positive amount.")
                if row.normalized_type not in {"income", "expense"}:
                    new_errors.append("Missing debit/credit transaction type.")
                if row.currency != "INR":
                    new_errors.append(f"Unsupported currency '{row.currency}'.")

                if row.duplicate_status in {"existing_reference_duplicate", "within_file_duplicate"}:
                    new_errors.append("Duplicate transaction reference cannot be imported.")
                    row.validation_status = "duplicate"
                    row.is_selected = False
                elif new_errors:
                    row.validation_status = "invalid"
                    row.is_selected = False
                else:
                    row.validation_status = "valid"
                    if req.is_selected is not None:
                        row.is_selected = req.is_selected
                    elif req.exclude is False:
                        row.is_selected = True
                row.validation_errors = new_errors

            if req.is_selected is not None and row.validation_status == "valid":
                row.is_selected = req.is_selected
            elif req.is_selected is True and row.validation_status != "valid":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot select row in '{row.validation_status}' state. Resolve issues or potential duplicate first.",
                )

            row.review_changes = changes or row.review_changes
            db.add(row)
            db.flush()

            all_rows = self.import_repo.list_all_rows(db, batch.id)
            self._recompute_batch_counts(batch, all_rows)
            self.import_repo.update_batch(db, batch)
            db.commit()
            refreshed = self.import_repo.get_row(db, batch.id, row.id, user.id)
            assert refreshed is not None
            return self._row_to_response(refreshed)
        except Exception:
            db.rollback()
            raise

    def review_duplicate(
        self,
        db: Session,
        user: User,
        batch_id: uuid.UUID,
        row_id: uuid.UUID,
        req: ImportDuplicateReviewRequest,
    ) -> ImportRowResponse:
        batch = self._get_owned_batch(db, user, batch_id)
        if batch.status != "ready_for_review":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Duplicates can only be reviewed when batch is ready for review.",
            )
        row = self.import_repo.get_row(db, batch.id, row_id, user.id)
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Import row not found.",
            )
        if row.validation_status not in {"potential_duplicate", "duplicate", "excluded", "valid"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Row status '{row.validation_status}' is not eligible for duplicate review.",
            )

        if req.decision == "import" and row.duplicate_status in {
            "existing_reference_duplicate",
            "within_file_duplicate",
        }:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Rows with duplicate external transaction references cannot be force-imported.",
            )

        try:
            if req.decision == "import":
                row.duplicate_status = "resolved_import"
                row.validation_status = "valid"
                row.is_selected = True
                row.validation_errors = []
            else:
                row.duplicate_status = "resolved_skip"
                row.validation_status = "excluded"
                row.is_selected = False

            changes = dict(row.review_changes or {})
            changes["duplicate_decision"] = req.decision
            row.review_changes = changes
            db.add(row)
            db.flush()

            all_rows = self.import_repo.list_all_rows(db, batch.id)
            self._recompute_batch_counts(batch, all_rows)
            self.import_repo.update_batch(db, batch)
            db.commit()
            refreshed = self.import_repo.get_row(db, batch.id, row.id, user.id)
            assert refreshed is not None
            return self._row_to_response(refreshed)
        except Exception:
            db.rollback()
            raise

    def bulk_select_rows(
        self,
        db: Session,
        user: User,
        batch_id: uuid.UUID,
        req: ImportBulkSelectRequest,
    ) -> ImportBatchResponse:
        batch = self._get_owned_batch(db, user, batch_id)
        if batch.status != "ready_for_review":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Row selection is only permitted while batch is ready for review.",
            )
        try:
            all_rows = self.import_repo.list_all_rows(db, batch.id)
            target_set = set(req.row_ids or [])
            for r in all_rows:
                if req.action == "select_all_valid":
                    if r.validation_status == "valid":
                        r.is_selected = True
                elif req.action == "deselect_all":
                    if r.validation_status != "imported":
                        r.is_selected = False
                elif req.action == "set_selection":
                    if r.id in target_set and r.validation_status == "valid":
                        r.is_selected = req.is_selected
                db.add(r)
            db.flush()
            self._recompute_batch_counts(batch, all_rows)
            self.import_repo.update_batch(db, batch)
            db.commit()
            return self._batch_to_response(self._get_owned_batch(db, user, batch.id))
        except Exception:
            db.rollback()
            raise

    def get_summary(self, db: Session, user: User, batch_id: uuid.UUID) -> ImportSummaryResponse:
        batch = self._get_owned_batch(db, user, batch_id)
        rows = self.import_repo.list_all_rows(db, batch.id)

        selected_rows = [r for r in rows if r.is_selected and r.validation_status == "valid"]
        selected_income = sum(
            (r.normalized_amount or Decimal("0.00"))
            for r in selected_rows
            if r.normalized_type == "income"
        )
        selected_expenses = sum(
            (r.normalized_amount or Decimal("0.00"))
            for r in selected_rows
            if r.normalized_type == "expense"
        )

        imported_rows_list = [r for r in rows if r.validation_status == "imported"]
        imported_income = sum(
            (r.normalized_amount or Decimal("0.00"))
            for r in imported_rows_list
            if r.normalized_type == "income"
        )
        imported_expenses = sum(
            (r.normalized_amount or Decimal("0.00"))
            for r in imported_rows_list
            if r.normalized_type == "expense"
        )

        return ImportSummaryResponse(
            batch_id=batch.id,
            status=batch.status,
            account_id=batch.account_id,
            account_name=batch.account.name if batch.account else "Account",
            account_type=batch.account.account_type if batch.account else "savings",
            total_rows=len(rows),
            valid_rows=sum(1 for r in rows if r.validation_status == "valid"),
            invalid_rows=sum(1 for r in rows if r.validation_status == "invalid"),
            needs_review_rows=sum(1 for r in rows if r.validation_status == "needs_review"),
            duplicate_rows=sum(1 for r in rows if r.validation_status == "duplicate"),
            potential_duplicate_rows=sum(
                1 for r in rows if r.validation_status == "potential_duplicate"
            ),
            excluded_rows=sum(1 for r in rows if r.validation_status == "excluded"),
            imported_rows=len(imported_rows_list),
            selected_rows=len(selected_rows),
            selected_income=Decimal(selected_income).quantize(Decimal("0.01")),
            selected_expenses=Decimal(selected_expenses).quantize(Decimal("0.01")),
            selected_net=Decimal(selected_income - selected_expenses).quantize(Decimal("0.01")),
            imported_income=Decimal(imported_income).quantize(Decimal("0.01")),
            imported_expenses=Decimal(imported_expenses).quantize(Decimal("0.01")),
            imported_net=Decimal(imported_income - imported_expenses).quantize(Decimal("0.01")),
        )

    def commit_import(
        self, db: Session, user: User, batch_id: uuid.UUID
    ) -> ImportCommitResponse:
        """
        Atomically commits all selected eligible ImportRow records through TransactionService
        and LedgerService. Protected against concurrent or repeated commits via row-level lock
        and explicit state transitions.
        """
        batch = self.import_repo.get_batch_for_update(db, batch_id, user.id)
        if not batch:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Import batch not found.",
            )

        if batch.status == "completed":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This import batch has already been completed.",
            )
        if batch.status != "ready_for_review":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Import batch cannot be committed in '{batch.status}' state.",
            )

        account = self.account_repo.get_by_id(db, batch.account_id, user.id)
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Destination account no longer exists.",
            )
        if account.status != "active":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Destination account is archived or disconnected.",
            )

        all_rows = self.import_repo.list_all_rows(db, batch.id)
        selected_valid = [
            r
            for r in all_rows
            if r.is_selected
            and r.validation_status == "valid"
            and r.imported_transaction_id is None
        ]
        if not selected_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No eligible selected rows to import.",
            )

        # Sort chronologically so credits occur prior to expenses when verifying balance
        selected_valid.sort(
            key=lambda r: (
                r.normalized_date or dt.date.min,
                0 if r.normalized_type == "income" else 1,
                r.source_row_number,
            )
        )

        import_source = f"{batch.file_type}_import"

        try:
            self._transition_state(batch, "importing", f"Committing {len(selected_valid)} rows.")
            db.flush()

            # Ensure system categories are seeded within transaction if needed
            self.category_service.seed_default_categories(db, commit=False)

            imported_count = 0
            imported_income = Decimal("0.00")
            imported_expenses = Decimal("0.00")

            for row in selected_valid:
                assert row.normalized_date is not None
                assert row.normalized_amount is not None
                assert row.normalized_type in {"income", "expense"}
                assert row.normalized_description is not None

                # Verify category compatibility if assigned
                cat_id = row.category_id
                if cat_id is not None:
                    cat = self.category_repo.get_by_id(db, cat_id, user.id)
                    if not cat or cat.category_type != row.normalized_type:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Row {row.source_row_number}: incompatible or missing category.",
                        )

                tx_req = TransactionCreateRequest(
                    account_id=account.id,
                    transaction_type=row.normalized_type,  # type: ignore[arg-type]
                    amount=row.normalized_amount,
                    currency=row.currency,
                    category_id=cat_id,
                    description=row.normalized_description,
                    merchant_payee=row.normalized_merchant,
                    transaction_date=row.normalized_date,
                    notes=row.normalized_notes
                    or f"Imported from {batch.original_filename} (Row {row.source_row_number})",
                )
                created_tx = self.transaction_service.create_transaction(
                    db=db,
                    user=user,
                    req=tx_req,
                    source=import_source,
                    external_reference=row.transaction_reference,
                    import_batch_id=batch.id,
                    import_row_id=row.id,
                    commit=False,
                )
                row.imported_transaction_id = created_tx.id
                row.validation_status = "imported"
                db.add(row)

                imported_count += 1
                if row.normalized_type == "income":
                    imported_income += row.normalized_amount
                else:
                    imported_expenses += row.normalized_amount

            db.flush()
            db.refresh(account)

            if account.account_type != "credit_card" and account.current_balance < Decimal("0.00"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Import would reduce '{account.name}' balance to -₹{abs(account.current_balance):,.2f}. "
                        "Verify opening balance or exclude excess expense rows before committing."
                    ),
                )

            # Update batch metrics & finalize state
            skipped_count = len(all_rows) - imported_count
            now = dt.datetime.now(dt.UTC)
            batch.imported_rows = imported_count
            batch.skipped_rows = skipped_count
            batch.total_income = imported_income.quantize(Decimal("0.01"))
            batch.total_expenses = imported_expenses.quantize(Decimal("0.01"))
            batch.completed_at = now
            self._recompute_batch_counts(batch, all_rows)
            self._transition_state(
                batch,
                "completed",
                f"Successfully imported {imported_count} transaction(s) into {account.name}.",
            )
            self.import_repo.update_batch(db, batch)
            db.commit()

            refreshed_batch = self._get_owned_batch(db, user, batch.id)
            summary = self.get_summary(db, user, batch.id)
            return ImportCommitResponse(
                batch=self._batch_to_response(refreshed_batch),
                summary=summary,
                imported_count=imported_count,
                skipped_count=skipped_count,
                message=f"Successfully imported {imported_count} transaction(s) into {account.name}.",
            )
        except Exception:
            db.rollback()
            raise

    def delete_or_cancel_batch(
        self, db: Session, user: User, batch_id: uuid.UUID
    ) -> dict[str, str]:
        batch = self._get_owned_batch(db, user, batch_id)
        if batch.status in {"completed", "completed_with_errors", "importing"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Completed import batches cannot be deleted to preserve financial audit history.",
            )

        storage_key = batch.storage_key
        try:
            self.import_repo.delete_batch(db, batch)
            db.commit()
        except Exception:
            db.rollback()
            raise

        if storage_key:
            self.storage.delete(storage_key)

        return {"message": "Import batch cancelled and uploaded file securely deleted."}
