# OCR Pipeline & Human Review Workflow (Phase 7)

## Provider-Independent Architecture
Implemented in `backend/app/services/documents/ocr_engine.py`:
- **Interface:** `OcrProvider` (`recognize_image_array`).
- **Default Local CPU Provider:** `RapidOcrProvider` executing local PaddleOCR PP-OCR models via `rapidocr` + `onnxruntime` (compatible with Python 3.14, zero paid cloud OCR APIs). Also includes `PaddleOcrNativeProvider` for Python environments where native `paddlepaddle` is installed.
- **Singleton Initialization:** OCR models are lazily initialized once per worker process using thread-safe locking (`get_ocr_provider()`), never reloaded per request.
- **PDF & Image Preprocessing:** `PyMuPDF` (`import pymupdf`) checks each PDF page for native selectable text first; image pages and scanned PDF pages are rendered page-by-page (capped by `DOCUMENT_MAX_PDF_PAGES`, default `20`), preprocessed via `OpenCV` (scaling, LAB CLAHE luminance normalization, denoising), and passed to the local OCR provider.

## Background Job Queue
- `document_processing_jobs` stores durable jobs claimed safely via PostgreSQL `FOR UPDATE SKIP LOCKED` in `DocumentOcrWorker`.
- Bounded `ThreadPoolExecutor` (`OCR_WORKER_MAX_CONCURRENT`, default `2`) keeps HTTP endpoints non-blocking.
- Stale `"processing"` jobs (>10 min) recover on restart; failures retry with exponential backoff up to `OCR_JOB_MAX_ATTEMPTS` (`3`).

## Deterministic Extraction & Indian GST Validation (`invoice_parser.py`)
- Extracts merchant metadata, invoice/bill numbers, DD/MM/YYYY & DD MMM YYYY dates, currency, subtotal, taxable amount, grand total, paid/outstanding balances, Indian GSTIN, CGST, SGST, IGST, tax %, and tabular line items.
- Missing financial values stay `NULL` (never coerced to `₹0.00`).
- Validation checks GSTIN format, calendar date validity, GST component sums, subtotal + tax vs grand total reconciliation, and line-item sum consistency, flagging arithmetic conflicts rather than silently modifying numbers.

## Human Review Workflow
`uploaded → queued → processing → needs_review → confirmed / rejected`
- OCR never automatically posts financial transactions or marks bills as paid.
- `raw_text` and `raw_structured_data` stay immutable while user corrections, field `accepted`/`rejected` decisions, and confirmation actions are logged in `document_review_events`.
