# Document Management & Private Storage (Phase 7)

## Overview
Phase 7 introduces a centralized private document vault (`financial_documents`) backed by PostgreSQL metadata and opaque UUID-based filesystem storage (`uploads/documents` via `PrivateDocumentStorage`).

## Supported Formats & Categories
- **Formats:** PDF (digital multi-page and scanned), JPG, JPEG, PNG, WebP.
- **Categories:** `electricity_bill`, `water_bill`, `gas_bill`, `internet_bill`, `mobile_bill`, `credit_card_statement`, `bank_statement`, `shopping_receipt`, `travel_receipt`, `medical_receipt`, `insurance`, `tax`, `loan`, `subscription_invoice`, `other`.

## Security & Validation
- Client MIME headers and untrusted filenames are never trusted.
- Every uploaded file is checked for extension allowlist, non-empty size (`<= DOCUMENT_MAX_FILE_SIZE_BYTES`), actual magic-byte file signature, and structural decode (`pymupdf` for PDF, `Pillow.Image.verify()` for images).
- Duplicate detection computes SHA-256 hashes (`file_hash`) per user, flagging identical re-uploads without destroying existing records.
- Stored files live under opaque UUID keys (`<user_id>/<uuid>.<ext>`) outside web-served directories, guarded against path traversal (`Path.is_relative_to`), served via authenticated downloads with `X-Content-Type-Options: nosniff`.
- Original file payloads remain untouched; OCR text and structured snapshots are stored separately in `document_extractions`.

## Traceable Financial Record Links
`document_links` connects confirmed documents to Phase 2–6 records (`bill`, `transaction`, `subscription`, `loan`) and enforces unique constraints preventing duplicate entity creation from the same document.
