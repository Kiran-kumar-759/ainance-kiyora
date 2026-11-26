# Phase 7 Security Controls

- **Authentication & CSRF:** All Document, OCR, and Email endpoints enforce HttpOnly session authentication (`get_current_user`) and double-submit `X-CSRF-Token` validation (`verify_csrf`) on mutations (`POST`, `PATCH`, `DELETE`).
- **OAuth State & Redirect Validation:** Gmail connect generates HMAC-SHA256 signed, expiring (`600s`), user-bound state (`oauth_state.py`) and enforces `GOOGLE_ALLOWED_REDIRECT_URIS`.
- **Token Protection:** OAuth access and refresh tokens are encrypted at rest with `Fernet` (`token_crypto.py`), stripped from all API responses and logs, and wiped/revoked on disconnect.
- **Private Storage & Traversal Prevention:** Documents use opaque UUID keys inside `DOCUMENT_STORAGE_DIR` (`doc_storage.py`), validate magic bytes + PDF/image structure, enforce size & rate limits (`DOCUMENT_UPLOAD_RATE_LIMIT_MAX`), sanitize filenames, serve downloads with `X-Content-Type-Options: nosniff`, and enforce `user_id` ownership (`404` on cross-user access).
- **Untrusted Content Handling:** Email HTML bodies have `<script>`/`<style>` removed and are converted to sanitized plain text (`strip_html_to_plain_text`); OCR outputs and email subjects never trigger direct SQL/HTML execution or automatic financial ledger mutations.

---

# Phase 10 Security Controls (AI Assistant, RAG, Web Research & Voice)

- **Tenant Isolation:** Conversations, messages, preferences, and RAG chunks enforce `user_id` ownership (`404` on cross-user IDs). Web provider API keys and `GROQ_API_KEY` live exclusively server-side (`config.py` / gitignored `.env`).
- **Read-Only Ledger Guarantee & Voice Draft Confirmation:** The assistant has read-only finance tool functions only (`finance_tools.py`). Spoken transcripts parsed via `/api/v1/assistant/voice/parse-expense` never touch ledger/transaction tables directly and always require explicit user review and Save confirmation in the UI.
- **SSRF & Prompt-Injection Defense:** External web URLs pass `is_safe_public_url` (rejecting non-HTTP/HTTPS schemes, `localhost`, `.local`, `.internal`, loopback, metadata, and private IP ranges). Untrusted web & OCR excerpts are stripped of control characters (`sanitize_untrusted_text`), bounded, and framed inside `<UNTRUSTED_EVIDENCE>` data-only delimiters.
- **No Private Data in Public Search & No Silent Provider Fallback:** `sanitize_public_search_query` removes long account/phone numbers and email addresses before calling external search APIs. Selected providers never fall back silently to another provider upon failure or missing credentials.

---

# Phase 11 Hardening Controls (Integration & Production Release Readiness)

- **HTTP Security Headers & Request Correlation:** All responses carry `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy: camera=(), microphone=(self), geolocation=()`, `X-XSS-Protection: 0`, and `X-Request-ID`. API endpoints include `Cache-Control: no-store`; HTTPS deployments (`COOKIE_SECURE=true`) emit HSTS.
- **Production Exposure & Host Controls:** OpenAPI/Swagger/ReDoc endpoints are disabled in `ENVIRONMENT=production`, CORS uses explicit allowlists, `ALLOWED_HOSTS` enables `TrustedHostMiddleware`, and `SECRET_KEY` length/wildcard CORS validation runs at settings startup.
- **Webhook SSRF Protection:** Outbound SMS notifications validate `SMS_WEBHOOK_URL` against `is_safe_public_url` with `follow_redirects=False`.
- **Stale Background Job Recovery & Shared Rate Limiting:** `IntelligenceRepository.claim_next_queued_job` recovers stale `processing` AI/forecasting jobs older than 10 minutes (`max_attempts` enforced) before `FOR UPDATE SKIP LOCKED` claiming, and `rate_limiter` supports Valkey shared counters with automatic in-memory fallback.

---

# Pre-Phase 12 Security Controls (Integrations & Settings Centers)

- **Zero Secret Leakage:** Integration overview, provider details, and connectivity tests never expose `GROQ_API_KEY`, `TAVILY_API_KEY`, `LANGSEARCH_API_KEY`, `FIRECRAWL_API_KEY`, `GOOGLE_OAUTH_CLIENT_SECRET`, `SMTP_PASSWORD`, `SMS_API_KEY`, `SMS_WEBHOOK_URL` query secrets, encrypted OAuth tokens, password hashes, or session tokens.
- **Rate Limits & CSRF on Sensitive Controls:** `POST /api/v1/integrations/providers/{provider_id}/test` (`10/min` per user) and `POST /api/v1/auth/change-password` (`5/min` per user) enforce HttpOnly auth, double-submit `verify_csrf`, and per-user rate limiting.
- **Cross-Tenant Isolation:** Integration connections (`GET/POST /api/v1/integrations/connections/{id}`) and individual session revocations verify ownership (`404` on foreign IDs).
- **Safe Disconnection & Account Deletion Boundaries:** Disconnecting Gmail or Demo Bank clears OAuth grants without deleting historical accounts, ledger entries, or documents; self-service destructive account deletion remains deferred cleanly rather than risking incomplete financial cascade removal.
