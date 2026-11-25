# Phase 7 Security Controls

- **Authentication & CSRF:** All Document, OCR, and Email endpoints enforce HttpOnly session authentication (`get_current_user`) and double-submit `X-CSRF-Token` validation (`verify_csrf`) on mutations (`POST`, `PATCH`, `DELETE`).
- **OAuth State & Redirect Validation:** Gmail connect generates HMAC-SHA256 signed, expiring (`600s`), user-bound state (`oauth_state.py`) and enforces `GOOGLE_ALLOWED_REDIRECT_URIS`.
- **Token Protection:** OAuth access and refresh tokens are encrypted at rest with `Fernet` (`token_crypto.py`), stripped from all API responses and logs, and wiped/revoked on disconnect.
- **Private Storage & Traversal Prevention:** Documents use opaque UUID keys inside `DOCUMENT_STORAGE_DIR` (`doc_storage.py`), validate magic bytes + PDF/image structure, enforce size & rate limits (`DOCUMENT_UPLOAD_RATE_LIMIT_MAX`), sanitize filenames, serve downloads with `X-Content-Type-Options: nosniff`, and enforce `user_id` ownership (`404` on cross-user access).
- **Untrusted Content Handling:** Email HTML bodies have `<script>`/`<style>` removed and are converted to sanitized plain text (`strip_html_to_plain_text`); OCR outputs and email subjects never trigger direct SQL/HTML execution or automatic financial ledger mutations.
