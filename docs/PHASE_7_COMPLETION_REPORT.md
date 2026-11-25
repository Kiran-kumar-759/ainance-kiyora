# PHASE 7 COMPLETION REPORT — DOCUMENTS, OCR, EMAIL & SMS INGESTION

**Project:** AI Personal Finance Manager — India  
**Phase:** 7 of 12  
**Date:** 2026-11-25  

---

## 1. Executive Summary

Phase 7 delivers a complete, PostgreSQL-backed **Document Vault, Local CPU OCR & Indian GST Extraction Pipeline, Human-in-the-Loop Review Workspace, Read-Only Gmail OAuth Sync & Duplicate Review Workflow, and Compliant SMS Integration Boundary**, seamlessly integrated into the existing Phases 0–6 FastAPI + React/TypeScript modular monolith without introducing LLM/AI agents, external paid OCR APIs, or automatic financial ledger mutations.

---

## 2. Actual Starting Git Branch and Commit

- **Starting Branch:** `feature/phase-6-subscriptions-loans`
- **Starting `HEAD` Commit:** `2024718` (`feat(phase-6): add provider logos, category/provider presets, subscription card boxes & updated report`)

## 3. Final Git Branch and Commit

- **Final Branch:** `feature/phase-6-subscriptions-loans` (preserved without unprompted branch switching per workspace safety rules)
- **Final Checkpoint:** Dedicated Phase 7 commit on `feature/phase-6-subscriptions-loans` (see final git log / reply hash for exact SHA).

## 4. Database Migration Revision

- **Revision:** `01139757d108` (`backend/alembic/versions/01139757d108_create_documents_ocr_email_ingestion_.py`)
- **Down Revision:** `1c2a8c9f2c32` (Phase 6 head)
- **Current Head:** `01139757d108 (head)`

## 5. Tables and Relationships Created

Ten normalized PostgreSQL tables with strict `user_id` foreign keys (`ON DELETE CASCADE`) and composite indexes:
1. `financial_documents` — Metadata, opaque unique `storage_key`, SHA-256 `file_hash`, `duplicate_flag`, `is_duplicate_of_id` self-FK, `document_category`, `source`, `processing_status`, `ocr_status`, `page_count`.
2. `document_processing_jobs` — Durable queue with partial unique index `uq_doc_job_active_per_doc` preventing concurrent duplicate active jobs per document/type.
3. `document_extractions` — 1:1 with `financial_documents`; separates immutable `raw_text` & `raw_structured_data` from editable invoice, INR monetary (`NUMERIC(19, 2)`), Indian GST, `line_items`, `field_confidence`, `field_decisions`, and validation lists.
4. `document_review_events` — Append-only audit log recording `uploaded`, `ocr_completed`, `fields_edited`, `confirmed`, `rejected`, `linked`, `bill_created`, and `transaction_created`.
5. `document_links` — Links to `bills`, `financial_transactions`, `subscriptions`, and `loans` with partial unique indexes (`uq_doc_link_bill`, `uq_doc_link_tx`, `uq_doc_link_sub`, `uq_doc_link_loan`).
6. `email_connections` — User OAuth connections (`uq_email_conn_user_provider`), Fernet-encrypted access/refresh tokens at rest, `last_history_id`, and `last_sync_at`.
7. `email_sync_history` — Per-sync metrics (`messages_scanned`, `relevant_messages`, `attachments_processed`, `duplicate_candidates`, `candidates_needing_review`, `failed_jobs`).
8. `email_message_records` — Sanitized plain-text email metadata (`uq_email_msg_user_provider_msg` on `(user_id, provider_message_id)`).
9. `email_attachment_records` — Attachment metadata, SHA-256 hash, and FK to stored `financial_documents`.
10. `email_document_candidates` — Extracted invoice candidates awaiting human confirmation (`needs_review`, `duplicate_warning`, `confirmed`, `rejected`).

## 6. Document Storage Implementation

- Implemented in `backend/app/services/documents/doc_storage.py` (`PrivateDocumentStorage`, `validate_uploaded_document`).
- Supports `.pdf`, `.png`, `.jpg`, `.jpeg`, `.webp` up to `DOCUMENT_MAX_FILE_SIZE_BYTES` (15 MB default).
- Never trusts client MIME types or filenames; checks magic-byte signatures, structural PDF/image integrity (`pymupdf` & `Pillow.Image.verify()`), computes SHA-256 hashes, saves files via opaque UUID storage keys `<user_id>/<uuid>.<ext>`, blocks path traversal, and serves downloads/previews only to the authenticated owner with `X-Content-Type-Options: nosniff`.

## 7. OCR Architecture and Supported Document Formats

- Implemented provider-independent `OcrProvider` interface in `backend/app/services/documents/ocr_engine.py`.
- **Environment Finding (Python 3.14.7):** `paddlepaddle` has no PyPI binary wheel for Python 3.14, so `OCR_ENGINE=rapidocr` uses **`RapidOcrProvider`** running official PaddleOCR PP-OCR ONNX models locally on CPU via `rapidocr` + `onnxruntime` + `opencv-python-headless` (plus `PaddleOcrNativeProvider` fallback when native `paddlepaddle` is present).
- Lazy singleton model initialization (`_CACHED_PROVIDER`), OpenCV preprocessing (`preprocess_image_for_ocr`: scaling, LAB CLAHE normalization, denoising), and page-by-page `PyMuPDF` (`import pymupdf`) handling for native digital PDFs, multi-page PDFs (capped by `DOCUMENT_MAX_PDF_PAGES=20`), scanned PDFs, and image receipts.

## 8. OCR Extraction Fields and Validation

- Implemented deterministically in `backend/app/services/documents/invoice_parser.py` (`parse_ocr_output`, `validate_extraction_consistency`).
- Extracts merchant name/address/phone, invoice/bill number, invoice/due/payment dates (`DD/MM/YYYY`, `DD MMM YYYY`, `YYYY-MM-DD`), bill period, document classification (`invoice` vs `receipt` vs `statement`), currency, `subtotal`, `taxable_amount`, `total_tax`, `grand_total`, `amount_paid`, `outstanding_amount`, Indian GST (`gstin`, `cgst`, `sgst`, `igst`, `tax_percentage`), line items, and per-field confidences.
- Missing financial amounts remain `None` (never coerced to `₹0.00`). Validation checks calendar dates, 15-char Indian GSTIN format, non-negative totals, GST component consistency, subtotal + tax vs grand total arithmetic, and line-item sum vs invoice totals, surfacing explicit warnings/errors without silent mutation.

## 9. Human Review Workflow

- Enforces `uploaded → queued → processing → needs_review → confirmed / rejected` in `DocumentService`.
- OCR never creates confirmed transactions or marks bills as paid automatically.
- Users compare side-by-side previews with extracted fields, accept/reject individual fields, edit fields, record audit diffs in `document_review_events` while keeping `raw_text` & `raw_structured_data` intact, reject with reason, or confirm cleanly.

## 10. Financial Linking Implementation

- Confirmation actions (`confirm_document`) support `standalone`, `create_bill` (`BillService.create_bill`, strictly unpaid), `create_transaction` (`TransactionService.create_transaction(..., commit=False)` in double-entry ledger), or linking existing `bill`, `transaction`, `subscription`, or `loan` records via `DocumentLink` with duplicate-creation guards (`find_created_link`).

## 11. Gmail OAuth and Synchronization Implementation

- Implemented across `token_crypto.py`, `oauth_state.py`, `gmail_adapter.py`, `email_ingestion_service.py`, and `routes/email.py`.
- Requests strictly read-only scope `https://www.googleapis.com/auth/gmail.readonly`, binds HMAC-SHA256 OAuth state to `user_id` and allowlisted `redirect_uri`, encrypts OAuth tokens at rest using `Fernet`, supports token refresh and disconnect/revocation, runs incremental `historyId` sync (falling back cleanly on expired `404` history IDs to controlled financial queries), sanitizes HTML to plain text, stores supported attachments in `PrivateDocumentStorage`, runs local OCR, and flags exact & uncertain recurring duplicates cleanly.
- Live Google mailbox sync requires real `GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET` credentials (unset locally).

## 12. SMS Integration Status and Limitations

- **Status:** Incoming SMS extraction is **explicitly unavailable** (`SMS_INGESTION_ENABLED=false`, `SMS_INGESTION_PROVIDER=none`, `GET /api/v1/email/sms/status` -> `available: false`).
- **Reason:** Pure browser SaaS applications cannot read Android SMS inboxes cleanly without a native Android companion app or telecom bridge. No inbox scraping, OS permission bypass, or fabricated SMS data exists. Phase 5 outgoing SMS bill reminders remain unaffected.

## 13. Background Job Architecture

- Implemented `DocumentOcrWorker` (`backend/app/services/documents/worker.py`) backed by PostgreSQL `document_processing_jobs` (`FOR UPDATE SKIP LOCKED`), bounded asyncio `ThreadPoolExecutor` (`OCR_WORKER_MAX_CONCURRENT=2`), FastAPI `BackgroundTasks` dispatch on upload/reprocess, stale-job crash recovery (>10 min), and exponential backoff retries up to `OCR_JOB_MAX_ATTEMPTS=3` (disabled automatically under `ENVIRONMENT=test` for deterministic tests).

## 14. API Endpoint Inventory

- **Documents (`/api/v1/documents`):** `POST /upload`, `GET ""`, `GET /overview`, `GET /processing-history`, `GET /{id}`, `DELETE /{id}`, `GET /{id}/download`, `GET /{id}/preview`, `POST /{id}/process`, `GET /{id}/processing-status`, `GET /{id}/extraction`, `PATCH /{id}/extraction`, `POST /{id}/confirm`, `POST /{id}/reject`, `POST /{id}/link`.
- **Email & SMS (`/api/v1/email`):** `GET /connections`, `GET /gmail/connect`, `GET /gmail/callback`, `POST /gmail/disconnect`, `POST /gmail/sync`, `GET /sync-history`, `GET /candidates`, `GET /candidates/{id}`, `POST /candidates/{id}/confirm`, `POST /candidates/{id}/reject`, `GET /sms/status`.

## 15. Frontend Screens and Workflows

- Implemented `DocumentsPage.tsx`, `OcrReviewModal.tsx`, `documentsApi.ts`, and `types/documents.ts`, integrated into `App.tsx` and `AppShell.tsx` (`Documents` navigation item activated, sidebar/header updated to `Phase 7`).
- Covers Overview metrics & recent uploads, Searchable/Filterable Grid & List Library with pagination, Drag-and-Drop Multi-File Upload, Needs Review queue, **Two-Panel OCR Review Workspace** (PDF page navigation + zoom + raw OCR toggle on left; editable fields + confidence badges + accept/reject toggles + validation warnings + line items + confirm/create/link controls on right), Email Imports (Gmail connect/disconnect, sync now, history, candidates, SMS boundary card), and Processing History with `Retry OCR`.

## 16. Security Implementation

- `get_current_user` (`401`), `verify_csrf` (`403`), per-user `404` resource isolation across metadata/download/preview/edit/confirm/delete/email candidates, upload & sync sliding-window rate limits (`InMemoryRateLimiter`), `Fernet` OAuth token encryption, HMAC OAuth state binding, path traversal blocking, magic-byte & structural file verification, `X-Content-Type-Options: nosniff`, and HTML script stripping.

## 17. Environment Variables

Added/documented in `.env.example`, `backend/.env.example`, and `docs/ENVIRONMENT.md`: `DOCUMENT_STORAGE_DIR`, `DOCUMENT_MAX_FILE_SIZE_BYTES`, `DOCUMENT_MAX_PDF_PAGES`, `OCR_ENGINE`, `OCR_USE_ANGLE_CLS`, `OCR_WORKER_ENABLED`, `OCR_WORKER_INTERVAL_SECONDS`, `OCR_WORKER_MAX_CONCURRENT`, `OCR_JOB_MAX_ATTEMPTS`, `DOCUMENT_UPLOAD_RATE_LIMIT_MAX`, `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `GOOGLE_OAUTH_REDIRECT_URI`, `GMAIL_SCOPES`, `EMAIL_TOKEN_ENCRYPTION_KEY`, `EMAIL_SYNC_DEFAULT_QUERY`, `EMAIL_SYNC_MAX_MESSAGES`, `SMS_INGESTION_ENABLED`, `SMS_INGESTION_PROVIDER`.

## 18. Data Population Strategy

- Zero fabricated documents, OCR extractions, email candidates, or SMS messages seeded into user accounts; integration tests create ephemeral users and clean up all DB rows and private storage directories after each test.

## 19. Backend Test Results

- `./venv/bin/pytest -q` (run against real PostgreSQL `pfm_test`): **68 passed, 0 failed** (11 Starlette deprecation warnings, 61.08s), including:
  - `tests/test_documents_ocr.py`: Private upload/validation/duplicate hash/traversal/IDOR/delete + real CPU `RapidOCR` PNG & scanned PDF + multi-page digital PDF + Indian GST validation conflicts + bounded retry + edit audit trail + human confirmation creating unpaid bill & double-entry ledger transaction.
  - `tests/test_email_sms_ingestion.py`: OAuth state validation, Fernet token encryption at rest, mocked Gmail full query & incremental `historyId` sync, HTML stripping, attachment OCR, recurring duplicate warning, `429` quota handling, cross-user isolation, disconnect revocation, and honest SMS unavailable boundary.

## 20. Frontend Test Results

- `npm test -- --run`: **8 test files passed, 35 tests passed, 0 failed** in `7.81s` (mocked API component & workflow tests, including `frontend/src/test/Documents.test.tsx`).

## 21. Ruff Results

- `./venv/bin/ruff check .`: **All checks passed!**

## 22. TypeScript and Production Build Results

- `npm run build` (`tsc && vite build`): **Passed** (`✓ 1617 modules transformed`, `dist/index.html`, CSS, JS bundles generated in `9.68s`).

## 23. PostgreSQL Migration Verification

- Verified `upgrade head` (`1c2a8c9f2c32 -> 01139757d108`) on `pfm_dev`, plus `upgrade head` -> `downgrade -1` -> `upgrade head` on `pfm_test`. `./venv/bin/alembic current` -> `01139757d108 (head)`.

## 24. Browser E2E Verification

- **Blocked (Not Verified Live):** Subagent `browser` could not connect to Chrome DevTools (`Could not find DevToolsActivePort for chrome at /home/ckirankumar/.config/google-chrome/DevToolsActivePort (ENOENT)`). All frontend workflows were tested via mocked Vitest suites (`npm test -- --run`) and compiled via `tsc && vite build`.

## 25. Previous-Phase Regression Results

- All **65 existing Phase 1–6 backend tests** and **33 existing Phase 1–6 frontend tests** passed alongside Phase 7 tests after final edits (`68/68` backend total, `35/35` frontend total).

## 26. Files Created and Modified

- **Backend Created:** `backend/alembic/versions/01139757d108_create_documents_ocr_email_ingestion_.py`, `backend/app/models/{documents,email_ingestion}.py`, `backend/app/schemas/{documents,email_ingestion}.py`, `backend/app/repositories/documents/{__init__,document_repository}.py`, `backend/app/repositories/email/{__init__,email_repository}.py`, `backend/app/services/documents/{__init__,doc_storage,ocr_engine,invoice_parser,worker,document_service}.py`, `backend/app/services/email/{__init__,token_crypto,oauth_state,gmail_adapter,email_ingestion_service}.py`, `backend/app/services/sms/{__init__,sms_ingestion_boundary}.py`, `backend/app/api/routes/{documents,email}.py`, `backend/tests/{test_documents_ocr,test_email_sms_ingestion}.py`.
- **Backend Modified:** `backend/app/core/config.py`, `backend/app/models/__init__.py`, `backend/app/api/api.py`, `backend/app/main.py`, `backend/requirements.txt`, `backend/pyproject.toml`, `backend/.env.example`, `.env.example`, `.gitignore`.
- **Frontend Created:** `frontend/src/types/documents.ts`, `frontend/src/services/documentsApi.ts`, `frontend/src/pages/documents/{DocumentsPage,OcrReviewModal}.tsx`, `frontend/src/test/Documents.test.tsx`.
- **Frontend Modified:** `frontend/src/app/App.tsx`, `frontend/src/layouts/AppShell.tsx`.

## 27. Documentation Created

- `docs/DOCUMENT_MANAGEMENT.md`, `docs/OCR_PROCESSING.md`, `docs/EMAIL_INTEGRATION.md`, `docs/SECURITY.md`, `docs/ENVIRONMENT.md`, `docs/API.md`, `docs/DATABASE.md`, `docs/PHASE_7_COMPLETION_REPORT.md`.

## 28. Known Issues and Technical Debt

- `paddlepaddle` binary wheels are unavailable on PyPI for Python 3.14.7, so local OCR defaults cleanly to PaddleOCR PP-OCR ONNX models via `RapidOCR` (`rapidocr`) + `onnxruntime` instead of native PaddlePaddle.
- Rate limiting uses existing `InMemoryRateLimiter` (single-process in-memory sliding window).
- Pre-existing untracked `hdfc_oct_2026_statement.csv` remains untouched in repository root.

## 29. Deferred Items

- Native Android SMS companion app / telecom SMS bridge (deferred; incoming SMS ingestion explicitly disabled in web SaaS).
- Outlook / IMAP non-Gmail mailbox providers (interface extensible cleanly via `EmailProviderAdapter`).
- LLM-based categorization, RAG, anomaly detection, and spending advice (deferred to Phases 8–10).

## 30. Phase 8 Readiness Assessment

Phase 7 is complete, modular, and PostgreSQL-verified. Clean structured OCR documents, immutable raw text, human-confirmed financial links, and read-only email ingestion boundaries are ready for Phase 8 intelligent categorization/insights when approved.
