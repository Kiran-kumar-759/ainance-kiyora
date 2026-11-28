# First-Time User Onboarding & Financial Data Setup — Backend Architecture & API Contracts

**Project:** AI Personal Finance Manager — India  
**Alembic Revision:** `a4dccf170d59` (`add_onboarding_state_machine_and_banking_lifecycle`, parent `c87faa90fd29`)  
**Scope:** Backend orchestration, database persistence, bank catalog & lifecycle, workspace initialization, and future frontend integration contracts.

---

## 1. First-Time User Onboarding Architecture

The onboarding lifecycle pairs PostgreSQL identity flags (`users.onboarding_completed`) with a dedicated 1:1 state-machine table (`user_onboarding_states`), regional preferences (`user_preferences`), and live queries across user-owned financial records (`banking_connections`, `financial_accounts`, `financial_transactions`, `import_batches`, `financial_documents`).

Logical state progression:
- `registered` → `profile_setup` → `financial_data_setup` → `data_processing` → `completed`
- Optional skip path: `financial_data_setup` → `skipped` → `data_processing` / `completed`
- Returning users: `login` → `GET /api/v1/onboarding/status` (`onboarding_completed=true`, `required_gate_view="dashboard"`) → Dashboard.

Transitions are validated server-side via `_VALID_STAGE_TRANSITIONS` in `backend/app/services/onboarding_service.py`. Repeated completion/initialization calls are idempotent, and incomplete onboarding resumes cleanly from PostgreSQL state after logout or session reload.

---

## 2. Existing Functionality Reused

- **Phase 1 Auth & Preferences (`auth_service.py`, `user_service.py`, `users.py`)**: Argon2id password hashing, HttpOnly opaque `pfm_session` cookie, HMAC double-submit `pfm_csrf` verification, India defaults (`INR`, `en-IN`, `Asia/Kolkata`, `DD/MM/YYYY`), `User.onboarding_completed`.
- **Phase 2 Accounts, Ledger & Demo Banking (`account_service.py`, `ledger_service.py`, `banking_service.py`, `demo_provider.py`)**: Manual account creation, Decimal(19,2) double-entry journals, `DemoBankingProvider`, consent & selective account import, idempotent sync.
- **Phase 3 Statement Imports (`import_service.py`)**: CSV/XLSX upload, private file storage, column mapping, validation, 3-layer deduplication, and atomic commit.
- **Phase 7 Documents & OCR (`document_service.py`)**: Private upload, validation, OCR job queueing, human extraction confirmation.
- **Phase 8–10 Intelligence, Forecasting & RAG (`categorization_service.py`, `forecast_service.py`, `rag_service.py`)**: Deterministic rule/ML categorization (`use_ai_fallback=False`), deterministic cash-flow forecast calculation when sufficient data exists, and PostgreSQL document RAG chunk indexing.

---

## 3. New Functionality Implemented

- `user_onboarding_states` model (`backend/app/models/onboarding.py`) and repository (`backend/app/repositories/onboarding_repository.py`).
- Searchable Indian Bank Institution Catalog (`backend/app/providers/banking/institution_catalog.py`) with honest live Account Aggregator vs demo availability flags and `/assets/banks/*.svg` logo references.
- Granular banking lifecycle states (`not_connected`, `initiated`, `awaiting_consent`, `accounts_discovered`, `awaiting_account_selection`, `synchronizing`, `connected`, `failed`, `disconnected`, `revoked`) on `BankingConnection`, plus `initiate`, `consent`, and `revoke` API endpoints.
- Consolidated readiness endpoint `GET /api/v1/onboarding/status` + `POST /api/v1/onboarding/profile`, `/financial-setup/select`, `/financial-setup/skip`, `/initialize`, `/initialize/retry`, `/initialization-status`, and `/dashboard-access`.
- Safe idempotent 6-step `WorkspaceInitializationService` (`backend/app/services/workspace_init_service.py`) with duplicate-run lock (`409 Conflict` while `in_progress`) and failure retry support.
- Optional strict dashboard enforcement query parameter `enforce_onboarding=true` on `/api/v1/finance/dashboard` and `/api/v1/analytics/dashboard` plus dedicated `GET /api/v1/onboarding/dashboard-access` returning `403` until onboarding completion.

---

## 4. API Call Sequences & Example Contracts

All mutations require an authenticated `pfm_session` cookie and matching `X-CSRF-Token` header + `pfm_csrf` cookie.

### A. New Registration and Onboarding Initialization
1. `POST /api/v1/auth/register` → `201 Created` (`UserOnboardingState` initialized at `current_stage="registered"`).
2. `POST /api/v1/auth/login` → `200 OK` (`user.onboarding_completed == false`).
3. `GET /api/v1/onboarding/status` → `200 OK`
```json
{
  "onboarding_completed": false,
  "dashboard_access_allowed": false,
  "required_gate_view": "onboarding",
  "current_stage": "registered",
  "completed_stages": ["registered"],
  "current_step": 1,
  "profile_completed": false,
  "financial_setup_status": "not_started",
  "selected_setup_method": null,
  "financial_setup_skipped": false,
  "has_active_banking_connection": false,
  "accounts_count": 0,
  "transactions_count": 0,
  "pending_import_batches_count": 0,
  "pending_documents_count": 0,
  "initialization_status": "not_started",
  "next_action": "complete_profile"
}
```
4. `POST /api/v1/onboarding/profile`
```json
{
  "first_name": "Aarav",
  "last_name": "Mehta",
  "phone_number": "+91 9876543210",
  "preferred_currency": "INR",
  "locale": "en-IN",
  "timezone": "Asia/Kolkata",
  "date_format": "DD/MM/YYYY",
  "monthly_budget": "45000.00",
  "monthly_income_range": "100000-150000",
  "financial_goals": ["Emergency Fund", "SIP"]
}
```
Response: `200 OK` (`current_stage="financial_data_setup"`, `profile_completed=true`, `next_action="choose_financial_setup"`).

### B. Bank Institution Catalog Listing & Search
`GET /api/v1/banking/institutions?search=hdfc`
```json
{
  "institutions": [
    {
      "bank_id": "hdfc_bank",
      "bank_name": "HDFC Bank",
      "short_name": "HDFC",
      "bank_code": "HDFC",
      "category": "private_sector",
      "logo_key": "hdfc",
      "logo_url": "/assets/banks/hdfc.svg",
      "supported_connection_methods": ["statement_import", "manual_account"],
      "provider_id": "account_aggregator",
      "provider_available": false,
      "live_supported": false,
      "is_demo": false,
      "connection_availability_status": "live_unavailable",
      "unavailable_reason": "Live RBI Account Aggregator / FIP gateway is not configured in this environment. Use CSV/XLSX statement import, manual account creation, or Demo Banking."
    }
  ],
  "total": 1,
  "live_aa_configured": false,
  "demo_available": true
}
```
Attempting live initiation when `ACCOUNT_AGGREGATOR_ENABLED=false`:
`POST /api/v1/banking/connections/initiate` with `{"bank_id": "hdfc_bank", "connection_method": "account_aggregator", "consent_given": true}` → `503 Service Unavailable`.

### C. Demo Banking Connection Lifecycle
1. `POST /api/v1/onboarding/financial-setup/select` → `{"setup_method": "bank_connect", "bank_id": "demo_national_bank"}`
2. `POST /api/v1/banking/connections/initiate` → `{"bank_id": "demo_national_bank", "connection_method": "demo", "consent_given": false}` (`lifecycle_state="awaiting_consent"`, `status="pending"`)
3. `POST /api/v1/banking/connections/{connection_id}/consent` → `{"consent_given": true, "consent_scope": "accounts,transactions"}` (`lifecycle_state="accounts_discovered"`, `status="connected"`)
4. `GET /api/v1/banking/connections/{connection_id}/accounts` (`lifecycle_state` moves to `"awaiting_account_selection"`)
5. `POST /api/v1/banking/connections/{connection_id}/accounts/import` → `{"account_ids": ["dnb_sav_001"], "trigger_initial_sync": true}` (`lifecycle_state="connected"`, imports real DB account & idempotent transactions)
6. `POST /api/v1/onboarding/initialize` → `200 OK` (`initialization_status="completed"`, `onboarding_completed=true`, `dashboard_access_allowed=true`).
7. Later disconnect/revoke: `POST /api/v1/banking/connections/{connection_id}/disconnect` or `/revoke`.

### D. Manual Bank Account Creation
1. `POST /api/v1/onboarding/financial-setup/select` → `{"setup_method": "manual_account"}`
2. `POST /api/v1/finance/accounts` → `{"name": "HDFC Primary Savings", "account_type": "savings", "institution_name": "HDFC Bank", "opening_balance": "50000.00"}` (`source="manual"`)
3. `POST /api/v1/onboarding/initialize` → verifies account ledger & activates dashboard.

### E. Statement Import Workflow
1. `POST /api/v1/onboarding/financial-setup/select` → `{"setup_method": "statement_import"}`
2. Ensure destination account exists (`POST /api/v1/finance/accounts`).
3. `POST /api/v1/imports/upload` (multipart CSV/XLSX + `account_id`)
4. `PUT /api/v1/imports/{import_id}/mapping` → `POST /api/v1/imports/{import_id}/validate` → `POST /api/v1/imports/{import_id}/commit`
5. `POST /api/v1/onboarding/initialize` → runs deterministic categorization & unlocks dashboard.

### F. Document Upload & OCR Review
1. `POST /api/v1/onboarding/financial-setup/select` → `{"setup_method": "document_upload"}`
2. `POST /api/v1/documents/upload` (PDF/PNG/JPG/WebP)
3. Review via `GET /api/v1/documents/{id}`, `PATCH /api/v1/documents/{id}/extraction`, `POST /api/v1/documents/{id}/confirm`
4. `POST /api/v1/onboarding/initialize` → reindexes document RAG chunks (`pending_documents_count` tracked in `/onboarding/status`).

### G. Skip Financial Setup & Enter Dashboard
1. `POST /api/v1/onboarding/financial-setup/skip` → `{"complete_onboarding": false, "reason": "Later"}`
2. `POST /api/v1/onboarding/initialize` → completes with 0 accounts, 0 transactions, `financial_setup_skipped=true`, `has_active_banking_connection=false`, `dashboard_access_allowed=true`.

### H. Returning-User Login & Dashboard Gate Check
1. `POST /api/v1/auth/login` → `user.onboarding_completed == true`
2. `GET /api/v1/onboarding/status` → `required_gate_view="dashboard"`, `next_action="go_to_dashboard"`, `dashboard_access_allowed=true`.
3. `GET /api/v1/onboarding/dashboard-access` → `200 OK` (or `403 Forbidden` while incomplete).
4. `GET /api/v1/analytics/dashboard?enforce_onboarding=true` and `GET /api/v1/finance/dashboard?enforce_onboarding=true` enforce server-side completion when enabled.

---

## 5. Error & Recovery Handling

- If any initialization step fails, `UserOnboardingState.initialization_status` persists as `"failed"` alongside `initialization_error` and the exact failing step key; `/onboarding/initialize` returns `500` and `/onboarding/initialize/retry` cleanly recovers and completes onboarding without duplicating records.
- Duplicate concurrent calls while `initialization_status == "in_progress"` return `409 Conflict`.
- Declining bank consent records `lifecycle_state="failed"` cleanly without touching financial ledger records.

---

## 6. Database Migration & Security

- Revision `a4dccf170d59` adds `user_onboarding_states` and extends `banking_connections` (`bank_id`, `connection_method`, `lifecycle_state`, `last_error`, `revoked_at`) non-destructively with server defaults and backfills.
- All endpoints require `get_current_user`, state mutations enforce `verify_csrf`, queries scope strictly by `user_id`, and no internet-banking passwords, PINs, OTPs, or provider secrets are stored or returned.
