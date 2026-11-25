# Gmail OAuth Ingestion & SMS Boundary (Phase 7)

## Module C: Gmail OAuth 2.0 Integration (`email_ingestion_service.py`, `gmail_adapter.py`)
- **Provider Scope:** Strictly read-only `https://www.googleapis.com/auth/gmail.readonly` (no send/modify permissions).
- **Google Cloud Console Setup:**
  1. Create a Google Cloud Project and enable the **Gmail API**.
  2. Configure an OAuth 2.0 Web Application client with authorized redirect URI matching `GOOGLE_OAUTH_REDIRECT_URI` (default `http://127.0.0.1:8000/api/v1/email/gmail/callback`).
  3. Set `GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET` in `backend/.env` and configure `EMAIL_TOKEN_ENCRYPTION_KEY` (32-byte URL-safe base64 Fernet key in production).
- **Security Controls:** HMAC-SHA256 signed state bound to `user_id` and allowlisted redirect URI, encrypted access/refresh tokens at rest via `cryptography.fernet.Fernet`, automatic near-expiry refresh, token revocation on disconnect, never returning tokens to frontend responses.
- **Sync & Review:** Supports incremental Gmail `historyId` sync with 404 history expiry fallback to controlled financial search queries (`EMAIL_SYNC_DEFAULT_QUERY`). Strips scripts/HTML from email content into plain text, validates/stores supported PDF/image attachments privately, runs local OCR, flags exact & uncertain recurring duplicates cleanly, and requires explicit human confirmation (`EmailDocumentCandidate`) before creating bills or transactions.

## Module D: SMS Integration Boundary (`sms_ingestion_boundary.py`)
- **Status:** Incoming SMS extraction is **explicitly unavailable** in this web SaaS runtime.
- **Rationale:** Web browsers cannot access Android SMS inboxes directly, and no native Android companion bridge or webhook telecom source is configured. The system does not scrape inboxes, bypass OS permissions, or fabricate SMS records.
- **Continuity:** Phase 5 outgoing SMS bill reminders (`SmsProviderAdapter`) continue operating independently without changes.
