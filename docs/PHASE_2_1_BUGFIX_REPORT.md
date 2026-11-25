# Phase 2.1 Bugfix Report: Financial Account, Demo Banking & Balance Integrity Repair

**Project:** AI Personal Finance Manager — India  
**Branch:** `fix/phase-2-account-banking`  
**Base Commit:** `8150c20` (on `main`)  
**Database:** PostgreSQL (`pfm_dev`, `pfm_test`)  

---

## 1. Original Symptoms

1. **Bug A — Manual Financial Account Creation & Persistence Failure:**
   - Submitting **Create Financial Account** returned HTTP 200 or failed with stale CSRF errors (`"CSRF token signature is invalid or forged."`), and newly created accounts failed to persist in PostgreSQL `pfm_dev` / did not appear after list refresh.
2. **Bug B — Simulated Banking Integration Failures:**
   - Connecting a simulated bank, importing discovered accounts, and synchronizing transactions failed to persist in `pfm_dev` across HTTP requests.
   - `connected_accounts_count` was omitted on connect/disconnect responses, invalid external account IDs were silently ignored on import, and no API endpoint or UI existed to inspect recorded `banking_sync_runs` sync history.
   - Errors popped up via blocking browser `alert()` dialogs instead of inline UI error banners/modals, and FastAPI Pydantic `422` validation arrays could serialize poorly in frontend error banners.
3. **Bug C — Negative Asset Account Balances Allowed During Transactions & Transfers:**
   - Recording an expense larger than an asset account's available balance (for example, `₹50,000.00` expense on `SBI Savings` holding `₹10,000.00`, resulting in `-₹40,500.00`) succeeded without validation in both backend services and frontend forms.

---

## 2. Root Causes

1. **Missing `db.commit()` in Phase 2 Transaction Boundaries (`pfm_dev` rolled back every write):**
   - `backend/app/db/session.py` configures `SessionLocal(autocommit=False)` and `get_db()` closes sessions without committing.
   - All Phase 2 repositories (`AccountRepository`, `BankingRepository`, `CategoryRepository`, `LedgerRepository`, `TransactionRepository`, `TransferRepository`) only called `db.flush()`, and none of the Phase 2 services called `db.commit()`. Consequently, every Phase 2 write operation rolled back on request completion in live FastAPI.
   - `backend/tests/conftest.py` masked this because `override_get_db` yielded a single shared `db_session` across all requests within a test, keeping uncommitted flushed rows visible in-session.
2. **Insufficient Atomic Rollback Boundaries Across Composable Banking Calls:**
   - Nested calls (e.g. `BankingService.import_accounts` -> `AccountService.create_account`, `BankingService.sync_connection` -> `TransactionService.create_transaction`) needed `commit: bool = True` so multi-account imports and multi-transaction syncs commit once atomically or roll back completely on partial failure.
3. **Missing Balance-Floor Guardrails for Asset Accounts:**
   - `TransactionService`, `TransferService`, and `AccountService.update_opening_balance` lacked server-side validation preventing asset accounts (`savings`, `current`, `cash`, `digital_wallet`, `other`) from dropping below `₹0.00` on expenses, transaction amount edits, income deletions, outgoing transfers, transfer reversals, or opening-balance reductions.
4. **Frontend Error Formatting, Session Expiry & Sync History Gaps:**
   - `financeApi.ts` / `authApi.ts` assumed `data.detail` was always a string rather than formatting Pydantic 422 error lists.
   - `AccountsPage.tsx`, `BankingPage.tsx`, `TransactionsPage.tsx`, and `TransfersPage.tsx` used `window.alert()` on certain failures and lacked expired-session (`401`) event handling or sync run history visibility.

---

## 3. Files Inspected & Modified

### Inspected
- `backend/app/db/session.py`, `backend/app/api/deps.py`, `backend/app/main.py`
- `backend/app/models/finance.py`, `backend/tests/conftest.py`
- `backend/app/providers/banking/demo_provider.py`
- `backend/app/repositories/finance/*`, `backend/app/services/finance/*`, `backend/app/services/banking/*`
- `frontend/src/app/App.tsx`, `frontend/src/context/AuthContext.tsx`, `frontend/src/services/authApi.ts`, `frontend/src/services/financeApi.ts`
- `frontend/src/pages/finance/*`, `frontend/src/pages/banking/BankingPage.tsx`, `frontend/src/pages/auth/LoginPage.tsx`

### Modified / Created
| File | Summary of Changes |
| :--- | :--- |
| `backend/app/schemas/finance/account.py` | Added blank-name `@field_validator`, `decimal_places=2`, and upper/lower `NUMERIC(19,2)` bounds on `opening_balance`. |
| `backend/app/schemas/finance/banking.py` | Added `BankingSyncRunResponse` schema for sync history API responses. |
| `backend/app/repositories/finance/account_repository.py` | Added `get_active_by_name_and_type` helper for duplicate active manual account detection. |
| `backend/app/services/finance/account_service.py` | Added atomic `db.commit()` / `db.rollback()`, `commit: bool = True` support, HTTP 409 duplicate check on manual creation, and non-negative balance guard on `update_opening_balance`. |
| `backend/app/services/finance/category_service.py` | Added atomic `db.commit()` / `db.rollback()` across seeding and custom category CRUD (`commit: bool = True` on `seed_default_categories`). |
| `backend/app/services/finance/transaction_service.py` | Added atomic `db.commit()` / `db.rollback()`, `commit: bool = True` support, and negative-balance prevention on manual expenses, edits (`amount`/`date` changes), and income deletions. |
| `backend/app/services/finance/transfer_service.py` | Added atomic `db.commit()` / `db.rollback()` and negative-balance prevention on outgoing transfers from asset accounts and on transfer reversals. |
| `backend/app/services/banking/banking_service.py` | Fixed atomic multi-account import and multi-transaction sync (`commit=False` on sub-calls, single outer commit/rollback), added unknown external ID HTTP 400 validation, duplicate ID deduplication, consistent `connected_accounts_count`, and `list_sync_runs()`. |
| `backend/app/api/routes/banking/connections.py` | Added `GET /api/v1/banking/connections/{connection_id}/sync-runs` endpoint. |
| `backend/tests/test_phase_2_1_regression.py` | Added 4 real multi-session PostgreSQL integration tests against `pfm_test` (using independent `TestingSessionLocal` per HTTP request). |
| `frontend/src/types/finance.ts` | Added `BankingSyncRun` TypeScript interface. |
| `frontend/src/services/authApi.ts` | Added `extractApiErrorMessage` (handles string + FastAPI 422 array errors) and `pfm:session-expired` event dispatch on 401. |
| `frontend/src/services/financeApi.ts` | Used `extractApiErrorMessage`, added `pfm:session-expired` dispatch on 401, and added `listBankingSyncRuns`. |
| `frontend/src/context/AuthContext.tsx` | Subscribed to `pfm:session-expired` to clear session state and surface expiration message. |
| `frontend/src/app/App.tsx` | Redirects protected views to `login` when `!authLoading && !isAuthenticated`. |
| `frontend/src/pages/auth/LoginPage.tsx` | Displays context-level session expiry notice when present. |
| `frontend/src/pages/finance/AccountsPage.tsx` | Added double-submit guard, opening-balance decimal validation, confirmed success banner, and removed `alert()`. |
| `frontend/src/pages/banking/BankingPage.tsx` | Removed all `alert()` dialogs, added inline modal/page errors, disconnect double-click guard, confirmed status messages, and Sync History modal. |
| `frontend/src/pages/finance/TransactionsPage.tsx` | Added asset balance sufficiency validation, auto-refreshed account balances in dropdown after mutations, and replaced `alert()` in delete modal with inline `formError`. |
| `frontend/src/pages/finance/TransfersPage.tsx` | Added asset balance sufficiency validation, double-submit guard, and inline `reversalError` replacing `alert()`. |
| `frontend/src/test/Finance.test.tsx` | Added 2 frontend regression tests covering account errors/success banners and full demo banking discovery/import/sync/history without `alert()`. |

---

## 4. Database Changes

- **Schema / Migrations:** No table structure changes were required (`alembic` revision remains `d816f0127538`). All 8 Phase 2 tables in `pfm_dev` and `pfm_test` already enforce `NUMERIC(19, 2)`, foreign keys, and partial unique index `uq_transactions_user_account_ext_ref`.

---

## 5. Verification Results

### Automated Checks Executed After Final Edit
- **Backend Linter (`cd backend && ./venv/bin/ruff check .`):** `All checks passed!`
- **Backend Integration Tests (`cd backend && ./venv/bin/pytest -v`):** **40 / 40 passed** against real PostgreSQL `pfm_test`, including 4 new regression tests in `backend/tests/test_phase_2_1_regression.py`:
  1. `test_real_multi_session_account_creation_all_types` (all 6 account types across separate HTTP sessions, balanced ledger check, 409 duplicate rejection, 422/403/401 validation)
  2. `test_partial_failure_rolls_back_atomically` (verifies zero orphan rows on manual ledger failure and mid-import account #2 failure)
  3. `test_real_multi_session_demo_banking_workflow` (all 3 providers, consent, connect, discover, unknown-ID 400, selective import, duplicate import idempotency, sync balance update, re-sync 0 duplicates, sync history runs, disconnect preservation + sync rejection, cross-user User B 404 isolation)
  4. `test_negative_balance_prevention_across_transactions_and_transfers` (blocks over-balance expense, over-balance transaction edit, below-net opening balance reduction, over-balance transfer, and income deletion causing negative balance)
- **Frontend Tests (`cd frontend && npm test`):** **19 / 19 passed** (`App.test.tsx`, `Auth.test.tsx`, `Finance.test.tsx`).
- **Frontend Production Build (`cd frontend && npm run build`):** `tsc && vite build` succeeded cleanly (`dist/assets/index-BfJmUEEr.js` built in 4.82s).

### Live Browser Testing Notes
- Automated headless browser verification (`Browser QA Tester`) was explicitly canceled by the user mid-session.
- Live manual testing in the running UI by the user confirmed that manual accounts (`SBI Savings`) and simulated bank imports/sync (`DNB Salary Savings Account`, `DNB Business Current Account`, `DPB Wealth Advantage Savings`, `DPB Millennia Titanium Credit Card`) now persist and render in `pfm_dev`, which also surfaced Bug C (`-₹40,500.00` balance on `SBI Savings`), subsequently repaired and covered by backend + frontend validation and regression tests.

---

## 6. Remaining Limitations

1. Because automated browser verification via the browser subagent was canceled by the user, end-to-end browser UI clicks after the negative-balance fix were verified through Vitest component tests and real PostgreSQL multi-session HTTP integration tests rather than automated Chromium playback.
2. Existing historical negative balances created prior to this fix (such as the user's existing `SBI Savings` row in `pfm_dev` caused by a `₹50,000.00` `Movie Theatre` expense on a `₹10,000.00` balance) are preserved per the non-destructive history invariant; deleting or editing that expense in **Transactions** restores the balance cleanly.
3. Single-page navigation in `frontend/src/app/App.tsx` still uses React state (`currentView`) rather than URL path syncing (`/accounts`, `/banking`), keeping `http://127.0.0.1:5173/` in the address bar as designed in Phase 0–2.

---

## 7. Final Acceptance Status

- Backend persistence, atomic rollbacks, simulated banking sync history, negative-balance prevention, multi-user isolation, and automated backend/frontend test suites + builds are **COMPLETE & PASSING**.
- Dedicated branch `fix/phase-2-account-banking` is ready for review prior to Phase 3.
