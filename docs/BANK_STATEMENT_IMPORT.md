# Bank Statement Import & Transaction Ingestion Architecture (Phase 3)

**Project:** AI Personal Finance Manager — India  
**Scope:** CSV & XLSX Statement Upload, Column Mapping, Validation, Duplicate Detection & Atomic Ledger Commit  
**Endpoints Prefix:** `/api/v1/imports`  

---

## 1. Overview

Phase 3 adds a deterministic, privacy-preserving bank statement ingestion workflow designed for Indian bank & credit card exports (`.csv` and `.xlsx`), integrated directly into the existing Phase 2 double-entry ledger engine (`TransactionService` + `LedgerService`).

Key properties:
- **Zero LLM/AI guesswork & no OCR/PDF parsing:** All date, INR decimal parsing, column mapping confirmation, validation, and duplicate detection are deterministic.
- **Private local storage (`uploads/statements/`):** Uploaded files are stored under generated UUID keys (`{user_id}/{batch_id}/{uuid}.{ext}`), never exposed via public URLs, and checked against path traversal.
- **Exact Financial Precision:** All amounts use Python `Decimal` and PostgreSQL `NUMERIC(19, 2)`.
- **Atomic Double-Entry Ledger Integration:** Committed rows flow through `TransactionService.create_transaction(..., source="csv_import" | "xlsx_import", commit=False)` with row-level `FOR UPDATE` batch locking and chronological balance validation.

---

## 2. Supported File Formats & Upload Validation

- **CSV (`.csv`)**:
  - UTF-8 and UTF-8 BOM (`utf-8-sig`) supported.
  - Automatic delimiter sniffing across `,`, `;`, `\t`, and `|`, with override support.
  - Quoted fields with embedded commas handled via Python `csv.reader`.
- **Excel (`.xlsx`)**:
  - Validated via ZIP magic signature (`PK\x03\x04`) and parsed using `openpyxl` (`read_only=True, data_only=True`).
  - Multi-sheet workbooks supported: automatically picks the first sheet containing valid transaction rows on initial inspection, and lets the user switch sheets or adjust header row index (`0`–`50`) interactively.
  - Supports native Excel serial dates and datetime cells cleanly.
- **Limits & Hardening**:
  - Max upload size: `10 MB` (`IMPORT_MAX_FILE_SIZE_BYTES`, returns `413` if exceeded).
  - Max rows per statement: `5,000` (`IMPORT_MAX_ROWS_PER_FILE`).
  - Filename path components stripped (`sanitize_filename`), empty/null-byte/spoofed files rejected (`400`), archived or foreign destination accounts rejected (`400`/`404`).

---

## 3. Workflow State Machine

`ImportBatch.status` enforces strict allowed state transitions:
1. `uploaded` -> `mapping_required` (initial structural inspection succeeds)
2. `mapping_required` -> `validating` -> `ready_for_review` (after user confirms column mapping via `PUT /api/v1/imports/{id}/mapping`)
3. `ready_for_review` <-> `mapping_required` / `validating` (users can remap columns, edit individual rows, toggle bulk/single selection, resolve potential duplicates, or exclude rows)
4. `ready_for_review` -> `importing` -> `completed` (atomic ledger commit via `POST /api/v1/imports/{id}/commit`)
5. Unimported batches (`uploaded`, `mapping_required`, `ready_for_review`, `failed`) can be cancelled/deleted via `DELETE /api/v1/imports/{id}`, which deletes DB records and removes the stored raw file. Completed batches cannot be deleted to preserve financial audit history.

---

## 4. Indian Normalization & Validation Rules

Implemented in `backend/app/services/imports/normalizer.py`:
- **Dates (`parse_indian_date`)**: Supports `DD/MM/YYYY`, `DD-MM-YYYY`, `DD MMM YYYY`, `YYYY-MM-DD`, `MM/DD/YYYY` (when selected), and Excel serial dates. `auto` prioritizes Indian `DD/MM/YYYY` convention. Invalid calendar dates (e.g. `31/02/2026`) mark the row `invalid`.
- **Amounts (`parse_decimal_amount`)**: Strips `₹`, `INR`, `Rs.`, `,`, and parentheses `(500.00)` / trailing `DR` / `CR`, quantizing to `Decimal("0.01")`. Malformed values are never coerced to zero.
- **Amount Layouts**:
  - `single`: Single signed amount column (`negative_is_expense` or `positive_is_expense`) with optional `Dr/Cr` indicator column override.
  - `split`: Separate `Debit` and `Credit` columns. Ambiguous rows with positive values in both Debit and Credit are marked `needs_review`.
- **Currency**: Defaults to `INR`. Non-INR rows are flagged as `invalid` (multi-currency accounts are out of Phase 3 scope).

---

## 5. Three-Layer Duplicate Detection

Implemented in `backend/app/services/imports/duplicate_detector.py`:
- **Layer A1 (Within-File Reference Match):** Repeated non-empty `transaction_reference` (e.g., UTR) within the same file -> flagged `duplicate` (`within_file_duplicate`), deselected.
- **Layer B1 (Existing DB Reference Match):** Matches `FinancialTransaction.external_reference` on the target `(user_id, account_id)` -> flagged `duplicate` (`existing_reference_duplicate`), deselected.
- **Layer B2 (Same File Re-upload Exact Match):** When an identical `file_hash` was already committed on the account, matching `(date, amount, type, canonical_description)` signatures are marked `duplicate` (`exact_match_duplicate`), deselected. Upload also records an audit notice in `lifecycle_history`.
- **Layer A2 / C (Potential Duplicates):** Same date + exact Decimal amount (+ canonical description or non-referenced same-day spend) without identical file/ref -> flagged `potential_duplicate` and deselected by default so legitimate duplicate purchases (e.g., two identical coffee purchases on the same day) can be explicitly reviewed and confirmed via `PATCH /api/v1/imports/{id}/rows/{row_id}/duplicate-review` (`"import"` vs `"skip"`).

---

## 6. Accounting & Balance Integrity

During `POST /api/v1/imports/{id}/commit`:
- Row-level lock (`SELECT ... FOR UPDATE`) on `ImportBatch` prevents concurrent or duplicate commits (`409 Conflict` if already `completed`/`importing`).
- Selected valid rows are sorted chronologically (`normalized_date` ascending, `income` before `expense` on the same date, then `source_row_number`).
- Category compatibility (`category_type == normalized_type`) is verified before posting.
- Every transaction posts through `TransactionService.create_transaction` (`source="csv_import"` or `"xlsx_import"`, recording `import_batch_id` and `import_row_id`), generating balanced double-entry `LedgerJournal` & `LedgerEntry` rows.
- **Asset vs. Credit Card Accounts:** Asset accounts (`savings`, `current`, `cash`, `digital_wallet`, `other`) fail and atomically roll back if total post-import balance drops below `₹0.00`. `credit_card` accounts allow expense charges to increase outstanding liability and payments/credits to reduce liability cleanly.

---

## 7. Key API Endpoints (`/api/v1/imports`)

| Method & Path | Purpose |
|---|---|
| `POST /api/v1/imports/upload` | Upload `.csv`/`.xlsx` statement (CSRF-protected multipart upload, 10 MB cap) |
| `GET /api/v1/imports` | Overview metrics + user import batch history |
| `GET /api/v1/imports/profiles` | List user's saved column mapping profiles |
| `GET /api/v1/imports/{import_id}` | Batch metadata & lifecycle history |
| `GET /api/v1/imports/{import_id}/preview` | Re-inspect sheet / header row / delimiter |
| `GET /api/v1/imports/{import_id}/columns` | Detected headers, sample rows, candidate & saved mappings |
| `PUT /api/v1/imports/{import_id}/mapping` | Save mapping (and optional profile), normalize rows, validate & check duplicates |
| `POST /api/v1/imports/{import_id}/validate` | Re-run validation & duplicate engine |
| `GET /api/v1/imports/{import_id}/rows` | Filter, search, sort & paginate normalized rows |
| `PATCH /api/v1/imports/{import_id}/rows/bulk-select` | Bulk `select_all_valid`, `deselect_all`, or `set_selection` |
| `PATCH /api/v1/imports/{import_id}/rows/{row_id}` | Edit row date/description/merchant/amount/type/category or exclude/include |
| `GET /api/v1/imports/{import_id}/duplicates` | List flagged duplicates & potential duplicates |
| `PATCH /api/v1/imports/{import_id}/rows/{row_id}/duplicate-review` | Resolve potential duplicate (`import` or `skip`) |
| `GET /api/v1/imports/{import_id}/summary` | Exact Decimal summary (`selected_income`, `selected_expenses`, `selected_net`) |
| `POST /api/v1/imports/{import_id}/commit` | Atomically commit selected valid rows to financial ledger |
| `DELETE /api/v1/imports/{import_id}` | Cancel unimported batch and delete privately stored file |
