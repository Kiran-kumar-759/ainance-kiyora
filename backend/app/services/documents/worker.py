import asyncio
import datetime as dt
import logging
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.documents import (
    DocumentExtraction,
    DocumentProcessingJob,
    DocumentReviewEvent,
    FinancialDocument,
)
from app.repositories.documents.document_repository import DocumentRepository
from app.services.documents.doc_storage import PrivateDocumentStorage
from app.services.documents.invoice_parser import parse_ocr_output
from app.services.documents.ocr_engine import OcrProvider, extract_document_text

logger = logging.getLogger(__name__)


class DocumentOcrWorker:
    """
    PostgreSQL-backed OCR job processor and asyncio lifespan worker.
    Uses FOR UPDATE SKIP LOCKED + ThreadPoolExecutor so heavy PDF/image OCR
    never blocks FastAPI API requests or double-processes documents.
    """

    def __init__(self):
        self._repo = DocumentRepository()
        self._storage = PrivateDocumentStorage()
        self._executor = ThreadPoolExecutor(
            max_workers=max(1, settings.OCR_WORKER_MAX_CONCURRENT),
            thread_name_prefix="ocr-worker",
        )
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self._worker_id = f"worker-{os.getpid()}"

    def process_job(
        self,
        db: Session,
        job: DocumentProcessingJob,
        *,
        ocr_provider: OcrProvider | None = None,
    ) -> FinancialDocument | None:
        doc = db.execute(
            select(FinancialDocument).where(
                FinancialDocument.id == job.document_id,
                FinancialDocument.user_id == job.user_id,
            )
        ).scalar_one_or_none()

        if not doc:
            job.status = "cancelled"
            job.error_message = "Target document missing."
            job.completed_at = dt.datetime.now(dt.UTC)
            db.add(job)
            db.commit()
            return None

        doc.processing_status = "processing"
        doc.ocr_status = "processing"
        db.add(doc)
        db.commit()

        t_start = time.monotonic()
        try:
            file_bytes = self._storage.read_bytes(doc.storage_key)
            ocr_out = extract_document_text(file_bytes, doc.file_type, provider=ocr_provider)
            parsed = parse_ocr_output(ocr_out)
            duration_ms = int((time.monotonic() - t_start) * 1000)

            existing_ext = db.execute(
                select(DocumentExtraction).where(DocumentExtraction.document_id == doc.id)
            ).scalar_one_or_none()
            ext_rec = existing_ext or DocumentExtraction(user_id=doc.user_id, document_id=doc.id)

            ext_rec.ocr_engine = ocr_out.engine_name
            ext_rec.ocr_engine_version = ocr_out.engine_version
            ext_rec.raw_text = ocr_out.full_text
            ext_rec.raw_structured_data = parsed.to_snapshot_dict()

            ext_rec.merchant_name = parsed.merchant_name
            ext_rec.merchant_address = parsed.merchant_address
            ext_rec.merchant_phone = parsed.merchant_phone
            ext_rec.invoice_number = parsed.invoice_number
            ext_rec.invoice_date = parsed.invoice_date
            ext_rec.due_date = parsed.due_date
            ext_rec.payment_date = parsed.payment_date
            ext_rec.bill_period = parsed.bill_period
            ext_rec.detected_document_type = parsed.detected_document_type
            ext_rec.currency = parsed.currency

            ext_rec.subtotal = parsed.subtotal
            ext_rec.taxable_amount = parsed.taxable_amount
            ext_rec.total_tax = parsed.total_tax
            ext_rec.grand_total = parsed.grand_total
            ext_rec.amount_paid = parsed.amount_paid
            ext_rec.outstanding_amount = parsed.outstanding_amount

            ext_rec.gstin = parsed.gstin
            ext_rec.cgst = parsed.cgst
            ext_rec.sgst = parsed.sgst
            ext_rec.igst = parsed.igst
            ext_rec.tax_percentage = parsed.tax_percentage

            ext_rec.line_items = parsed.line_items
            ext_rec.field_confidence = parsed.field_confidence
            if not existing_ext:
                ext_rec.field_decisions = {}
            ext_rec.validation_errors = list(dict.fromkeys(parsed.validation_errors))
            ext_rec.validation_warnings = list(
                dict.fromkeys([*ocr_out.warnings, *parsed.validation_warnings])
            )
            ext_rec.overall_confidence = parsed.overall_confidence
            ext_rec.processing_metadata = {
                "duration_ms": duration_ms,
                "total_pages": ocr_out.total_pages,
                "processed_pages": ocr_out.processed_pages,
                "pages": [
                    {
                        "page_number": p.page_number,
                        "used_ocr": p.used_ocr,
                        "line_count": len(p.lines),
                        "average_confidence": p.average_confidence,
                    }
                    for p in ocr_out.pages
                ],
            }
            ext_rec.extracted_at = dt.datetime.now(dt.UTC)
            db.add(ext_rec)

            doc.page_count = ocr_out.total_pages
            doc.ocr_status = "completed"
            doc.processing_status = "needs_review"
            doc.processed_at = dt.datetime.now(dt.UTC)
            db.add(doc)

            job.status = "completed"
            job.error_message = None
            job.completed_at = dt.datetime.now(dt.UTC)
            db.add(job)

            db.add(
                DocumentReviewEvent(
                    user_id=doc.user_id,
                    document_id=doc.id,
                    action="ocr_completed",
                    changes={
                        "engine": ocr_out.engine_name,
                        "pages_processed": ocr_out.processed_pages,
                        "overall_confidence": str(parsed.overall_confidence),
                    },
                    notes="Extraction completed cleanly and queued for human review.",
                )
            )
            db.commit()
            return doc
        except Exception as exc:
            db.rollback()
            now = dt.datetime.now(dt.UTC)
            refreshed_job = db.execute(
                select(DocumentProcessingJob).where(DocumentProcessingJob.id == job.id)
            ).scalar_one_or_none()
            refreshed_doc = db.execute(
                select(FinancialDocument).where(FinancialDocument.id == doc.id)
            ).scalar_one_or_none()
            err_msg = f"{type(exc).__name__}: {str(exc)}"[:800]
            if refreshed_job:
                if refreshed_job.attempt_count < refreshed_job.max_attempts:
                    backoff = 30 * (2 ** max(0, refreshed_job.attempt_count - 1))
                    refreshed_job.status = "queued"
                    refreshed_job.error_message = err_msg
                    refreshed_job.next_retry_at = now + dt.timedelta(seconds=backoff)
                    if refreshed_doc:
                        refreshed_doc.ocr_status = "queued"
                        refreshed_doc.processing_status = "queued"
                else:
                    refreshed_job.status = "failed"
                    refreshed_job.error_message = err_msg
                    refreshed_job.completed_at = now
                    if refreshed_doc:
                        refreshed_doc.ocr_status = "failed"
                        refreshed_doc.processing_status = "failed"
                db.add(refreshed_job)
                if refreshed_doc:
                    db.add(refreshed_doc)
                db.commit()
            logger.error("Document OCR job %s failed cleanly: %s", job.id, err_msg)
            return refreshed_doc

    def process_pending_batch(
        self,
        db: Session,
        *,
        limit: int | None = None,
        ocr_provider: OcrProvider | None = None,
    ) -> int:
        jobs = self._repo.claim_due_jobs(
            db,
            worker_id=self._worker_id,
            limit=limit or settings.OCR_WORKER_MAX_CONCURRENT,
        )
        db.commit()
        processed = 0
        for job in jobs:
            self.process_job(db, job, ocr_provider=ocr_provider)
            processed += 1
        return processed

    def process_document_job_by_id(
        self,
        job_id: uuid.UUID,
        *,
        ocr_provider: OcrProvider | None = None,
    ) -> None:
        """Executes a specific queued job cleanly in a dedicated DB session (safe for BackgroundTasks)."""
        db = SessionLocal()
        try:
            now = dt.datetime.now(dt.UTC)
            job = db.execute(
                select(DocumentProcessingJob)
                .where(
                    DocumentProcessingJob.id == job_id,
                    DocumentProcessingJob.status == "queued",
                )
                .with_for_update(skip_locked=True)
            ).scalar_one_or_none()
            if not job:
                return
            job.status = "processing"
            job.attempt_count += 1
            job.started_at = now
            job.worker_id = f"bg-{self._worker_id}"
            db.add(job)
            db.commit()
            self.process_job(db, job, ocr_provider=ocr_provider)
        except Exception as exc:
            logger.error("Background OCR dispatch failure for job %s: %s", job_id, exc)
        finally:
            db.close()

    async def _loop(self) -> None:
        interval = max(5, settings.OCR_WORKER_INTERVAL_SECONDS)
        logger.info("Document OCR background worker started (interval=%ss).", interval)
        loop = asyncio.get_running_loop()
        while not self._stop_event.is_set():
            try:
                def _run_sync():
                    db = SessionLocal()
                    try:
                        return self.process_pending_batch(db)
                    finally:
                        db.close()

                await loop.run_in_executor(self._executor, _run_sync)
            except Exception as exc:
                logger.error("Document OCR worker loop error: %s", exc)
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=interval)
            except TimeoutError:
                pass

    def start(self) -> None:
        if (
            not settings.OCR_WORKER_ENABLED
            or settings.ENVIRONMENT.lower() == "test"
            or self._task is not None
        ):
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task is not None:
            self._stop_event.set()
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except Exception:
                self._task.cancel()
            self._task = None
        self._executor.shutdown(wait=False)


document_ocr_worker = DocumentOcrWorker()
