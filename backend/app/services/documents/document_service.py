import datetime as dt
import math
import uuid
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.documents import (
    DocumentExtraction,
    DocumentLink,
    DocumentProcessingJob,
    DocumentReviewEvent,
    FinancialDocument,
)
from app.models.user import User
from app.repositories.bills.bill_repository import BillRepository
from app.repositories.documents.document_repository import DocumentRepository
from app.repositories.finance.account_repository import AccountRepository
from app.repositories.finance.category_repository import CategoryRepository
from app.repositories.finance.transaction_repository import TransactionRepository
from app.repositories.loans.loan_repository import LoanRepository
from app.repositories.subscriptions.subscription_repository import SubscriptionRepository
from app.schemas.bills import BillCreateRequest
from app.schemas.documents import (
    DocumentConfirmRequest,
    DocumentExtractionResponse,
    DocumentExtractionUpdateRequest,
    DocumentLinkRequest,
    DocumentLinkResponse,
    DocumentListResponse,
    DocumentOverviewResponse,
    DocumentProcessingHistoryResponse,
    DocumentProcessingJobResponse,
    DocumentRejectRequest,
    DocumentReviewEventResponse,
    FinancialDocumentDetailResponse,
    FinancialDocumentSummaryResponse,
)
from app.schemas.finance.transaction import TransactionCreateRequest
from app.services.bills.bill_service import BillService
from app.services.documents.doc_storage import (
    DOCUMENT_CATEGORIES,
    PrivateDocumentStorage,
    validate_uploaded_document,
)
from app.services.documents.invoice_parser import (
    ParsedInvoiceResult,
    validate_extraction_consistency,
)
from app.services.documents.ocr_engine import render_document_preview_png
from app.services.finance.transaction_service import TransactionService


def _bill_cat_from_doc_cat(doc_cat: str) -> str:
    mapping = {
        "electricity_bill": "electricity",
        "water_bill": "water",
        "gas_bill": "gas",
        "internet_bill": "internet",
        "mobile_bill": "mobile_postpaid",
        "credit_card_statement": "credit_card",
        "insurance": "insurance",
        "loan": "loan_emi",
    }
    return mapping.get(doc_cat, "other")


class DocumentService:
    """
    Centralized service managing private financial documents, OCR job queueing,
    human extraction editing, audit trails, and atomic confirmation linking
    to existing Phase 2-6 financial records.
    """

    def __init__(self):
        self.repo = DocumentRepository()
        self.storage = PrivateDocumentStorage()
        self.bill_repo = BillRepository()
        self.tx_repo = TransactionRepository()
        self.account_repo = AccountRepository()
        self.category_repo = CategoryRepository()
        self.sub_repo = SubscriptionRepository()
        self.loan_repo = LoanRepository()
        self.bill_service = BillService()
        self.transaction_service = TransactionService()

    def _link_to_response(self, link: DocumentLink) -> DocumentLinkResponse:
        label = None
        if link.target_type == "bill" and link.bill:
            label = link.bill.bill_name
        elif link.target_type == "transaction" and link.transaction:
            label = link.transaction.description
        elif link.target_type == "subscription" and link.subscription:
            label = link.subscription.subscription_name
        elif link.target_type == "loan" and link.loan:
            label = link.loan.loan_name
        return DocumentLinkResponse(
            id=link.id,
            target_type=link.target_type,
            link_role=link.link_role,
            bill_id=link.bill_id,
            transaction_id=link.transaction_id,
            subscription_id=link.subscription_id,
            loan_id=link.loan_id,
            target_label=label,
            created_at=link.created_at,
        )

    def _to_summary(self, doc: FinancialDocument) -> FinancialDocumentSummaryResponse:
        ext = doc.extraction
        return FinancialDocumentSummaryResponse(
            id=doc.id,
            original_filename=doc.original_filename,
            file_type=doc.file_type,
            content_type=doc.content_type,
            file_size=doc.file_size,
            file_hash=doc.file_hash,
            document_category=doc.document_category,
            source=doc.source,
            is_duplicate_of_id=doc.is_duplicate_of_id,
            duplicate_flag=doc.duplicate_flag,
            processing_status=doc.processing_status,
            ocr_status=doc.ocr_status,
            page_count=doc.page_count,
            rejection_reason=doc.rejection_reason,
            uploaded_at=doc.uploaded_at,
            processed_at=doc.processed_at,
            confirmed_at=doc.confirmed_at,
            rejected_at=doc.rejected_at,
            links=[self._link_to_response(lk) for lk in (doc.links or [])],
            merchant_name=ext.merchant_name if ext else None,
            grand_total=ext.grand_total if ext else None,
            invoice_date=ext.invoice_date if ext else None,
            due_date=ext.due_date if ext else None,
        )

    def _to_detail(self, doc: FinancialDocument) -> FinancialDocumentDetailResponse:
        base = self._to_summary(doc)
        return FinancialDocumentDetailResponse(
            **base.model_dump(),
            extraction=(
                DocumentExtractionResponse.model_validate(doc.extraction)
                if doc.extraction
                else None
            ),
            jobs=[
                DocumentProcessingJobResponse(
                    id=j.id,
                    document_id=j.document_id,
                    document_filename=doc.original_filename,
                    job_type=j.job_type,
                    status=j.status,
                    attempt_count=j.attempt_count,
                    max_attempts=j.max_attempts,
                    next_retry_at=j.next_retry_at,
                    started_at=j.started_at,
                    completed_at=j.completed_at,
                    error_message=j.error_message,
                    created_at=j.created_at,
                )
                for j in (doc.jobs or [])
            ],
            review_events=[
                DocumentReviewEventResponse.model_validate(ev) for ev in (doc.review_events or [])
            ],
        )

    def upload_document(
        self,
        db: Session,
        user: User,
        *,
        filename: str | None,
        file_bytes: bytes,
        document_category: str = "other",
        source: str = "manual_upload",
        enqueue_ocr: bool = True,
    ) -> tuple[FinancialDocumentDetailResponse, uuid.UUID | None]:
        cat = document_category.strip().lower() if document_category else "other"
        if cat not in DOCUMENT_CATEGORIES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported document category '{document_category}'.",
            )

        try:
            validated = validate_uploaded_document(filename, file_bytes)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        existing_dup = self.repo.get_by_hash(db, user.id, validated.file_hash)
        storage_key = self.storage.save(user.id, validated.file_type, file_bytes)

        doc = FinancialDocument(
            user_id=user.id,
            original_filename=validated.safe_filename,
            file_type=validated.file_type,
            content_type=validated.content_type,
            file_size=validated.file_size,
            file_hash=validated.file_hash,
            storage_key=storage_key,
            document_category=cat,
            source=source,
            is_duplicate_of_id=existing_dup.id if existing_dup else None,
            duplicate_flag=existing_dup is not None,
            processing_status="queued" if enqueue_ocr else "uploaded",
            ocr_status="queued" if enqueue_ocr else "pending",
            page_count=validated.page_count,
        )
        self.repo.create(db, doc)

        queued_job_id: uuid.UUID | None = None
        if enqueue_ocr:
            job = DocumentProcessingJob(
                user_id=user.id,
                document_id=doc.id,
                job_type="ocr_extract",
                status="queued",
                max_attempts=settings.OCR_JOB_MAX_ATTEMPTS,
                idempotency_key=f"ocr-{doc.id}-{uuid.uuid4().hex[:8]}",
            )
            self.repo.create_job(db, job)
            queued_job_id = job.id

        self.repo.add_review_event(
            db,
            DocumentReviewEvent(
                user_id=user.id,
                document_id=doc.id,
                action="uploaded",
                changes={
                    "filename": validated.safe_filename,
                    "duplicate_flag": doc.duplicate_flag,
                    "file_hash": validated.file_hash,
                },
            ),
        )
        db.commit()
        db.expire_all()
        loaded = self.repo.get_by_id(db, doc.id, user.id)
        assert loaded is not None
        return self._to_detail(loaded), queued_job_id

    def get_overview(self, db: Session, user: User) -> DocumentOverviewResponse:
        counts = self.repo.get_overview_counts(db, user.id)
        recent = self.repo.list_recent(db, user.id, limit=6)
        return DocumentOverviewResponse(
            **counts,
            recent_documents=[self._to_summary(d) for d in recent],
        )

    def list_documents(
        self,
        db: Session,
        user: User,
        *,
        category: str | None = None,
        status_filter: str | None = None,
        ocr_status: str | None = None,
        source: str | None = None,
        search: str | None = None,
        date_from: dt.date | None = None,
        date_to: dt.date | None = None,
        linked_target_type: str | None = None,
        linked_target_id: uuid.UUID | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> DocumentListResponse:
        items, total = self.repo.list_documents(
            db,
            user.id,
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
        total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
        return DocumentListResponse(
            items=[self._to_summary(d) for d in items],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    def get_document(
        self, db: Session, user: User, doc_id: uuid.UUID
    ) -> FinancialDocumentDetailResponse:
        doc = self.repo.get_by_id(db, doc_id, user.id)
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
        return self._to_detail(doc)

    def get_download_payload(
        self, db: Session, user: User, doc_id: uuid.UUID
    ) -> tuple[FinancialDocument, bytes]:
        doc = self.repo.get_by_id(db, doc_id, user.id)
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
        try:
            payload = self.storage.read_bytes(doc.storage_key)
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Stored document file is no longer present on disk.",
            ) from exc
        return doc, payload

    def get_preview_png(
        self, db: Session, user: User, doc_id: uuid.UUID, *, page: int = 1
    ) -> tuple[bytes, int]:
        doc, payload = self.get_download_payload(db, user, doc_id)
        try:
            png_bytes, total_pages = render_document_preview_png(
                payload, doc.file_type, page_number=page
            )
            return png_bytes, total_pages
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unable to generate preview for document: {exc}",
            ) from exc

    def delete_document(self, db: Session, user: User, doc_id: uuid.UUID) -> None:
        from app.services.assistant.rag_service import purge_document_chunks

        doc = self.repo.get_by_id(db, doc_id, user.id)
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
        storage_key = doc.storage_key
        purge_document_chunks(db, user.id, doc.id)
        db.delete(doc)
        db.commit()
        self.storage.delete(storage_key)

    def enqueue_processing(
        self, db: Session, user: User, doc_id: uuid.UUID
    ) -> tuple[DocumentProcessingJobResponse, uuid.UUID | None]:
        doc = self.repo.get_by_id(db, doc_id, user.id)
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
        active = self.repo.get_active_job(db, doc.id, "ocr_extract")
        if active:
            return (
                DocumentProcessingJobResponse(
                    id=active.id,
                    document_id=active.document_id,
                    document_filename=doc.original_filename,
                    job_type=active.job_type,
                    status=active.status,
                    attempt_count=active.attempt_count,
                    max_attempts=active.max_attempts,
                    next_retry_at=active.next_retry_at,
                    started_at=active.started_at,
                    completed_at=active.completed_at,
                    error_message=active.error_message,
                    created_at=active.created_at,
                ),
                active.id if active.status == "queued" else None,
            )

        job = DocumentProcessingJob(
            user_id=user.id,
            document_id=doc.id,
            job_type="ocr_extract",
            status="queued",
            max_attempts=settings.OCR_JOB_MAX_ATTEMPTS,
            idempotency_key=f"ocr-{doc.id}-{uuid.uuid4().hex[:8]}",
        )
        self.repo.create_job(db, job)
        doc.processing_status = "queued"
        doc.ocr_status = "queued"
        db.add(doc)
        db.commit()
        return (
            DocumentProcessingJobResponse(
                id=job.id,
                document_id=job.document_id,
                document_filename=doc.original_filename,
                job_type=job.job_type,
                status=job.status,
                attempt_count=job.attempt_count,
                max_attempts=job.max_attempts,
                next_retry_at=job.next_retry_at,
                started_at=job.started_at,
                completed_at=job.completed_at,
                error_message=job.error_message,
                created_at=job.created_at,
            ),
            job.id,
        )

    def get_processing_status(
        self, db: Session, user: User, doc_id: uuid.UUID
    ) -> dict[str, Any]:
        doc = self.repo.get_by_id(db, doc_id, user.id)
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
        latest_job = doc.jobs[0] if doc.jobs else None
        return {
            "document_id": str(doc.id),
            "processing_status": doc.processing_status,
            "ocr_status": doc.ocr_status,
            "latest_job": (
                DocumentProcessingJobResponse(
                    id=latest_job.id,
                    document_id=latest_job.document_id,
                    document_filename=doc.original_filename,
                    job_type=latest_job.job_type,
                    status=latest_job.status,
                    attempt_count=latest_job.attempt_count,
                    max_attempts=latest_job.max_attempts,
                    next_retry_at=latest_job.next_retry_at,
                    started_at=latest_job.started_at,
                    completed_at=latest_job.completed_at,
                    error_message=latest_job.error_message,
                    created_at=latest_job.created_at,
                )
                if latest_job
                else None
            ),
        }

    def list_processing_history(
        self, db: Session, user: User
    ) -> DocumentProcessingHistoryResponse:
        rows = self.repo.list_jobs(db, user.id, limit=60)
        items = [
            DocumentProcessingJobResponse(
                id=job.id,
                document_id=job.document_id,
                document_filename=fname,
                job_type=job.job_type,
                status=job.status,
                attempt_count=job.attempt_count,
                max_attempts=job.max_attempts,
                next_retry_at=job.next_retry_at,
                started_at=job.started_at,
                completed_at=job.completed_at,
                error_message=job.error_message,
                created_at=job.created_at,
            )
            for job, fname in rows
        ]
        return DocumentProcessingHistoryResponse(items=items, total=len(items))

    def get_extraction(
        self, db: Session, user: User, doc_id: uuid.UUID
    ) -> DocumentExtractionResponse:
        doc = self.repo.get_by_id(db, doc_id, user.id)
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
        if not doc.extraction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Extraction data not available yet for this document.",
            )
        return DocumentExtractionResponse.model_validate(doc.extraction)

    def update_extraction(
        self,
        db: Session,
        user: User,
        doc_id: uuid.UUID,
        req: DocumentExtractionUpdateRequest,
    ) -> FinancialDocumentDetailResponse:
        doc = self.repo.get_by_id(db, doc_id, user.id)
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
        if doc.processing_status == "rejected":
            raise HTTPException(status_code=400, detail="Cannot edit a rejected document.")

        ext = doc.extraction
        if not ext:
            ext = DocumentExtraction(
                user_id=user.id,
                document_id=doc.id,
                ocr_engine="manual_review",
                raw_text=None,
                raw_structured_data=None,
            )
            db.add(ext)
            db.flush()

        editable_fields = [
            "merchant_name",
            "merchant_address",
            "merchant_phone",
            "invoice_number",
            "invoice_date",
            "due_date",
            "payment_date",
            "bill_period",
            "detected_document_type",
            "currency",
            "subtotal",
            "taxable_amount",
            "total_tax",
            "grand_total",
            "amount_paid",
            "outstanding_amount",
            "gstin",
            "cgst",
            "sgst",
            "igst",
            "tax_percentage",
        ]

        diff: dict[str, dict[str, Any]] = {}
        decisions = dict(ext.field_decisions or {})
        payload_data = req.model_dump(exclude_unset=True)

        for field_name in editable_fields:
            if field_name not in payload_data:
                continue
            new_val = payload_data[field_name]
            old_val = getattr(ext, field_name)
            if old_val != new_val:
                diff[field_name] = {
                    "old": str(old_val) if old_val is not None else None,
                    "new": str(new_val) if new_val is not None else None,
                }
                setattr(ext, field_name, new_val)
                decisions[field_name] = "edited"

        if "line_items" in payload_data and payload_data["line_items"] is not None:
            new_items = [
                {
                    "description": it["description"],
                    "quantity": str(it["quantity"]) if it.get("quantity") is not None else None,
                    "unit_price": str(it["unit_price"]) if it.get("unit_price") is not None else None,
                    "total": str(it["total"]) if it.get("total") is not None else None,
                }
                for it in payload_data["line_items"]
            ]
            if new_items != (ext.line_items or []):
                diff["line_items"] = {"old_count": len(ext.line_items or []), "new_count": len(new_items)}
                ext.line_items = new_items
                decisions["line_items"] = "edited"

        if "field_decisions" in payload_data and payload_data["field_decisions"]:
            for k, v in payload_data["field_decisions"].items():
                decisions[k] = v
                diff[f"decision:{k}"] = {"decision": v}

        ext.field_decisions = decisions

        # Re-run deterministic consistency validation on edited values
        check = ParsedInvoiceResult(
            merchant_name=ext.merchant_name,
            invoice_number=ext.invoice_number,
            invoice_date=ext.invoice_date,
            due_date=ext.due_date,
            subtotal=ext.subtotal,
            taxable_amount=ext.taxable_amount,
            total_tax=ext.total_tax,
            grand_total=ext.grand_total,
            gstin=ext.gstin,
            cgst=ext.cgst,
            sgst=ext.sgst,
            igst=ext.igst,
            line_items=list(ext.line_items or []),
        )
        validate_extraction_consistency(check)
        ext.validation_errors = check.validation_errors
        ext.validation_warnings = check.validation_warnings
        db.add(ext)

        if doc.processing_status in {"uploaded", "extracted", "queued"}:
            doc.processing_status = "needs_review"
            db.add(doc)

        if diff or req.notes:
            self.repo.add_review_event(
                db,
                DocumentReviewEvent(
                    user_id=user.id,
                    document_id=doc.id,
                    action="fields_edited",
                    changes=diff,
                    notes=req.notes,
                ),
            )
        db.commit()
        db.expire_all()
        loaded = self.repo.get_by_id(db, doc.id, user.id)
        assert loaded is not None
        return self._to_detail(loaded)

    def _create_link_record(
        self,
        db: Session,
        user: User,
        doc: FinancialDocument,
        *,
        target_type: str,
        target_id: uuid.UUID,
        link_role: str = "supporting_document",
    ) -> DocumentLink:
        # Validate target ownership strictly before linking
        kwargs: dict[str, Any] = {}
        if target_type == "bill":
            target = self.bill_repo.get_bill(db, target_id, user.id)
            if not target:
                raise HTTPException(status_code=404, detail="Target bill not found.")
            kwargs["bill_id"] = target.id
        elif target_type == "transaction":
            target = self.tx_repo.get_by_id(db, target_id, user.id)
            if not target:
                raise HTTPException(status_code=404, detail="Target transaction not found.")
            kwargs["transaction_id"] = target.id
        elif target_type == "subscription":
            target = self.sub_repo.get_by_id(db, target_id, user.id)
            if not target:
                raise HTTPException(status_code=404, detail="Target subscription not found.")
            kwargs["subscription_id"] = target.id
        elif target_type == "loan":
            target = self.loan_repo.get_by_id(db, target_id, user.id)
            if not target:
                raise HTTPException(status_code=404, detail="Target loan not found.")
            kwargs["loan_id"] = target.id
        else:
            raise HTTPException(status_code=400, detail="Invalid link target_type.")

        existing = self.repo.get_link(db, doc.id, target_type, target_id)
        if existing:
            return existing

        link = DocumentLink(
            user_id=user.id,
            document_id=doc.id,
            target_type=target_type,
            link_role=link_role,
            **kwargs,
        )
        db.add(link)
        db.flush()
        return link

    def link_document(
        self, db: Session, user: User, doc_id: uuid.UUID, req: DocumentLinkRequest
    ) -> FinancialDocumentDetailResponse:
        doc = self.repo.get_by_id(db, doc_id, user.id)
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
        self._create_link_record(
            db, user, doc, target_type=req.target_type, target_id=req.target_id
        )
        self.repo.add_review_event(
            db,
            DocumentReviewEvent(
                user_id=user.id,
                document_id=doc.id,
                action="linked",
                changes={"target_type": req.target_type, "target_id": str(req.target_id)},
            ),
        )
        db.commit()
        db.expire_all()
        loaded = self.repo.get_by_id(db, doc.id, user.id)
        assert loaded is not None
        return self._to_detail(loaded)

    def reject_document(
        self, db: Session, user: User, doc_id: uuid.UUID, req: DocumentRejectRequest
    ) -> FinancialDocumentDetailResponse:
        from app.services.assistant.rag_service import purge_document_chunks

        doc = self.repo.get_by_id(db, doc_id, user.id)
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
        doc.processing_status = "rejected"
        doc.rejected_at = dt.datetime.now(dt.UTC)
        doc.rejection_reason = req.reason.strip()
        purge_document_chunks(db, user.id, doc.id)
        db.add(doc)
        self.repo.add_review_event(
            db,
            DocumentReviewEvent(
                user_id=user.id,
                document_id=doc.id,
                action="rejected",
                changes={"reason": doc.rejection_reason},
                notes=doc.rejection_reason,
            ),
        )
        db.commit()
        db.expire_all()
        loaded = self.repo.get_by_id(db, doc.id, user.id)
        assert loaded is not None
        return self._to_detail(loaded)

    def confirm_document(
        self, db: Session, user: User, doc_id: uuid.UUID, req: DocumentConfirmRequest
    ) -> FinancialDocumentDetailResponse:
        doc = self.repo.get_by_id(db, doc_id, user.id)
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
        if doc.processing_status == "rejected":
            raise HTTPException(status_code=400, detail="Cannot confirm a rejected document.")

        ext = doc.extraction
        action = req.action

        if action == "create_bill":
            if self.repo.find_created_link(db, doc.id, "bill"):
                raise HTTPException(
                    status_code=400,
                    detail="A bill has already been created from this document.",
                )
            amt = req.amount or (ext.grand_total if ext else None)
            due = req.due_date or (ext.due_date if ext else None) or (ext.invoice_date if ext else None) or dt.date.today()
            name = req.bill_name or (ext.merchant_name if ext and ext.merchant_name else doc.original_filename)
            bill_cat = req.bill_category or _bill_cat_from_doc_cat(doc.document_category)
            bill_req = BillCreateRequest(
                bill_name=name[:150],
                bill_category=bill_cat,  # type: ignore[arg-type]
                provider_name=ext.merchant_name if ext else None,
                account_reference=ext.invoice_number if ext else None,
                description=req.notes or f"Created from document {doc.original_filename}",
                bill_type="one_time",
                is_variable_amount=amt is None,
                expected_amount=amt,
                current_amount=amt,
                currency="INR",
                due_date=due,
                financial_category_id=req.financial_category_id,
                linked_account_id=req.financial_account_id,
            )
            created_bill = self.bill_service.create_bill(db, user, bill_req)
            # Re-fetch doc cleanly after BillService committed
            doc = self.repo.get_by_id(db, doc_id, user.id)
            assert doc is not None
            self._create_link_record(
                db,
                user,
                doc,
                target_type="bill",
                target_id=created_bill.id,
                link_role="created_from_document",
            )
            self.repo.add_review_event(
                db,
                DocumentReviewEvent(
                    user_id=user.id,
                    document_id=doc.id,
                    action="bill_created",
                    changes={"bill_id": str(created_bill.id), "bill_name": created_bill.bill_name},
                ),
            )

        elif action == "create_transaction":
            if self.repo.find_created_link(db, doc.id, "transaction"):
                raise HTTPException(
                    status_code=400,
                    detail="A financial transaction has already been created from this document.",
                )
            if not req.financial_account_id:
                raise HTTPException(
                    status_code=400,
                    detail="financial_account_id is required when creating a transaction.",
                )
            amt = req.amount or (ext.grand_total if ext else None)
            if amt is None or amt <= Decimal("0.00"):
                raise HTTPException(
                    status_code=400,
                    detail="A positive monetary amount is required to create a transaction.",
                )
            tx_date = (
                req.transaction_date
                or (ext.payment_date if ext else None)
                or (ext.invoice_date if ext else None)
                or dt.date.today()
            )
            desc = (
                req.description
                or (f"{ext.merchant_name} ({ext.invoice_number})" if ext and ext.merchant_name and ext.invoice_number else None)
                or (ext.merchant_name if ext and ext.merchant_name else doc.original_filename)
            )
            tx_req = TransactionCreateRequest(
                account_id=req.financial_account_id,
                transaction_type=req.transaction_type,
                amount=amt,
                currency="INR",
                category_id=req.financial_category_id,
                description=desc[:250],
                merchant_payee=ext.merchant_name if ext else None,
                transaction_date=tx_date,
                notes=req.notes or f"Confirmed from document {doc.original_filename}",
            )
            created_tx = self.transaction_service.create_transaction(
                db=db,
                user=user,
                req=tx_req,
                source="manual",
                external_reference=f"doc:{doc.id}",
                commit=False,
            )
            self._create_link_record(
                db,
                user,
                doc,
                target_type="transaction",
                target_id=created_tx.id,
                link_role="created_from_document",
            )
            self.repo.add_review_event(
                db,
                DocumentReviewEvent(
                    user_id=user.id,
                    document_id=doc.id,
                    action="transaction_created",
                    changes={"transaction_id": str(created_tx.id), "amount": str(amt)},
                ),
            )

        elif action.startswith("link_"):
            target_type = action.removeprefix("link_")
            if not req.target_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"target_id is required for action '{action}'.",
                )
            self._create_link_record(
                db,
                user,
                doc,
                target_type=target_type,
                target_id=req.target_id,
                link_role="supporting_document",
            )

        doc.processing_status = "confirmed"
        doc.confirmed_at = dt.datetime.now(dt.UTC)
        db.add(doc)
        self.repo.add_review_event(
            db,
            DocumentReviewEvent(
                user_id=user.id,
                document_id=doc.id,
                action="confirmed",
                changes={"action": action},
                notes=req.notes,
            ),
        )
        db.commit()
        db.expire_all()
        loaded = self.repo.get_by_id(db, doc.id, user.id)
        assert loaded is not None
        return self._to_detail(loaded)
