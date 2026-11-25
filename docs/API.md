# Financial Analytics & Reporting API Documentation (Phase 4)

**Base URL:** `/api/v1`  
**Authentication:** Required on all endpoints (`pfm_session` HttpOnly cookie via `get_current_user`).  
**Monetary Encoding:** Exact decimal strings (`NUMERIC(19, 2)` / Python `Decimal`), currency `INR`.  
**Date Format:** ISO `YYYY-MM-DD` in JSON query/response bodies; `DD/MM/YYYY` in CSV exports.  

---

## 1. Analytics Endpoints (`/api/v1/analytics`)

- `GET /api/v1/analytics/dashboard`
  - Query: `period` (`this_week`, `this_month`, `last_month`, `last_3_months`, `last_6_months`, `this_quarter`, `last_quarter`, `this_year`, `last_year`, `all_time`, `custom`), `start_date`, `end_date`
  - Returns: `AnalyticsDashboardResponse` (net financial position, assets, liabilities, period totals, comparisons, income vs expense series, spending by category, 6-month trend, account balances, recent transactions, calculation traceability).
- `GET /api/v1/analytics/income`
  - Query: `period`, `start_date`, `end_date`, `granularity` (`daily`, `weekly`, `monthly`, `quarterly`), `account_id`, `source`
  - Returns: `IncomeAnalyticsResponse`
- `GET /api/v1/analytics/expenses`
  - Query: `period`, `start_date`, `end_date`, `granularity`, `account_id`, `source`
  - Returns: `ExpenseAnalyticsResponse` (includes `average_daily_spend`, `average_monthly_spend`, `largest_expenses`)
- `GET /api/v1/analytics/cashflow`
  - Query: `period`, `start_date`, `end_date`, `granularity`, `account_id`
  - Returns: `CashFlowAnalyticsResponse`
- `GET /api/v1/analytics/categories`
  - Query: `category_type` (`expense` | `income`), `period`, `start_date`, `end_date`, `account_id`, `source`
  - Returns: `CategoryAnalyticsResponse`
- `GET /api/v1/analytics/trends`
  - Query: `period`, `start_date`, `end_date`, `granularity`, `account_id`
  - Returns: `TrendAnalyticsResponse` (series, top 4 category trends, ledger-reconstructed `balance_history`)
- `GET /api/v1/analytics/comparisons`
  - Query: `comparison_preset` (`month_over_month`, `quarter_over_quarter`, `year_over_year`, `last_3_months`, `custom`), `start_date`, `end_date`, `account_id`
  - Returns: `PeriodComparisonResponse` (current/previous bounds, metrics, deltas, `partial_period_warning`, category shifts)
- `GET /api/v1/analytics/accounts`
  - Query: `period`, `start_date`, `end_date`
  - Returns: `AccountAnalyticsListResponse`
- `GET /api/v1/analytics/accounts/{account_id}`
  - Query: `period`, `start_date`, `end_date`, `granularity`
  - Returns: `AccountAnalyticsDetailResponse` (`404` if account does not belong to user or is disconnected)

---

## 2. Reporting & Export Endpoints (`/api/v1/reports`)

- `GET /api/v1/reports` — Lists all 8 supported report definitions.
- `GET /api/v1/reports/summary` — Monthly Financial Summary
- `GET /api/v1/reports/income` — Income Report
- `GET /api/v1/reports/expenses` — Expense Report
- `GET /api/v1/reports/categories` — Category-Wise Spending Report
- `GET /api/v1/reports/accounts` — Account-Wise Activity Report
- `GET /api/v1/reports/cashflow` — Cash-Flow Report
- `GET /api/v1/reports/savings` — Savings Report
- `GET /api/v1/reports/transactions` — Transaction Summary Report
- `GET /api/v1/reports/export/csv` — Streams UTF-8 CSV (`text/csv`) with `DD/MM/YYYY` dates, INR decimals, active filters, and spreadsheet formula injection escaping.

---

## 3. Bills, Payments, Schedules & Reminders (`/api/v1/bills` — Phase 5)

Mutating endpoints (`POST`, `PATCH`, `PUT`, `DELETE`) require `X-CSRF-Token` alongside the authenticated session cookie.

- `POST /api/v1/bills` (`201`) — Create one-time or recurring bill (fixed or variable amount) and schedule reminders.
- `GET /api/v1/bills` — Paginated bills list with filters (`status_filter`, `bill_category`, `bill_type`, `start_date`, `end_date`, `search`, `sort_by`, `include_archived`, `page`, `page_size`).
- `GET /api/v1/bills/overview` — Aggregated counts (`upcoming_count`, `due_soon_count`, `overdue_count`, `paid_count`), known `INR` totals, `unknown_variable_bills_count`, `next_payment_due`, recent payments, unread notifications count.
- `GET /api/v1/bills/upcoming`, `GET /api/v1/bills/overdue`, `GET /api/v1/bills/paid` — Status-focused endpoints.
- `GET /api/v1/bills/{bill_id}`, `PATCH /api/v1/bills/{bill_id}`, `POST /api/v1/bills/{bill_id}/archive` — Details, edits (re-syncs pending reminders on due-date changes), and soft archival preserving payment history & ledger records.
- `POST /api/v1/bills/{bill_id}/payments` — Records a manually completed payment atomically into `FinancialTransaction` (`source="bill_payment"`) + double-entry `LedgerJournal`/`LedgerEntry`, or executes `FinancialTransfer` semantics for linked `credit_card` bills without double-counting expenses; supports `idempotency_key` and auto-spawns next recurring occurrence when settled.
- `POST /api/v1/bills/{bill_id}/payments/link-transaction` — Attaches an existing expense/transfer transaction without creating duplicate ledger rows.
- `GET /api/v1/bills/{bill_id}/payments`, `GET /api/v1/bills/payments` — Payment history per bill or across all bills.
- `GET /api/v1/bills/schedules`, `PATCH /api/v1/bills/schedules/{schedule_id}`, `POST /api/v1/bills/schedules/{schedule_id}/generate-next` — Manage recurring templates (`weekly`, `monthly`, `quarterly`, `half_yearly`, `yearly`, `custom`), end dates, active toggles, and idempotent next-occurrence generation.
- `PUT /api/v1/bills/{bill_id}/reminders`, `POST /api/v1/bills/reminders/process` — Configure reminder offsets/channels and run idempotent multi-channel reminder dispatch (`in_app`, `email`, `sms`).
- `POST /api/v1/bills/{bill_id}/documents` (`201`), `GET /api/v1/bills/{bill_id}/documents/{doc_id}/download` — Private supporting document upload (`.pdf`, `.png`, `.jpg`, `.jpeg`, `.csv`, `.xlsx` up to 10 MB) and authenticated download (`X-Content-Type-Options: nosniff`).

---

## 4. In-App Notifications (`/api/v1/notifications` — Phase 5)

- `GET /api/v1/notifications` (`unread_only` query flag) — Lists persistent in-app notifications with `unread_count`.
- `GET /api/v1/notifications/unread-count` — Returns `{ "unread_count": int }`.
- `PATCH /api/v1/notifications/{notification_id}/read` — Marks single notification read (`404` if not owned by user).
- `POST /api/v1/notifications/read-all` — Marks all user notifications read.

---

## 5. OTT & Subscription Management (`/api/v1/subscriptions` — Phase 6)

- `POST /api/v1/subscriptions` (`201`) — Register a subscription (or free trial) with optional amount and reminder schedule.
- `GET /api/v1/subscriptions` — Paginated list with filters (`status_filter`, `category`, `search`, `sort_by`, `include_archived`).
- `GET /api/v1/subscriptions/overview`, `GET /api/v1/subscriptions/analytics` — Normalized monthly/annual recurring projections vs actual historical spend, category/provider breakdown, trend, and price changes.
- `GET /api/v1/subscriptions/{id}`, `PATCH /api/v1/subscriptions/{id}` — Details and updates (automatically logs price changes).
- `POST /api/v1/subscriptions/{id}/price-change` — Records dated price revision (`previous_price` → `new_price`) preserving past payments.
- `POST /api/v1/subscriptions/{id}/pause`, `/resume`, `/cancel`, `/archive`, `/advance-renewal` — Full lifecycle controls with reminder sync/cancellation.
- `POST /api/v1/subscriptions/{id}/payments`, `/payments/link-transaction`, `/payments/{payment_id}/reverse`, `GET /payments` — Atomic ledger-backed subscription expense payments (`idempotency_key`) and reversals.
- `PUT /api/v1/subscriptions/{id}/reminders` — Update renewal/trial reminder offsets & channels.
- `GET /api/v1/subscriptions/candidates`, `POST /api/v1/subscriptions/candidates/decision` — Deterministic recurring expense candidates requiring user review (`ignore` / `link`).

---

## 6. Loan & EMI Management (`/api/v1/loans` — Phase 6)

- `POST /api/v1/loans/calculator` — Deterministic `Decimal` EMI & amortization preview (`reducing_balance`, `flat_rate`, `zero_interest`).
- `POST /api/v1/loans` (`201`) — Register a newly disbursed or mid-tenure existing loan (creates `loan_liability` ledger account + amortization installments).
- `GET /api/v1/loans`, `/overview`, `/analytics`, `/payments` — Loan dashboard totals, breakdown, progress, and repayment history.
- `GET /api/v1/loans/{id}`, `PATCH /api/v1/loans/{id}`, `POST /api/v1/loans/{id}/archive` — Details, metadata edits, and archival.
- `POST /api/v1/loans/{id}/rate-revision` — Floating/fixed interest rate update preserving historical paid installments and regenerating unpaid schedule (`recalculate_emi` or `adjust_tenure`).
- `POST /api/v1/loans/{id}/prepayment-scenario` — Hypothetical lump-sum / extra EMI / fee simulation (read-only, zero DB/ledger side effects).
- `POST /api/v1/loans/{id}/payments`, `/payments/link-transaction`, `/payments/{payment_id}/reverse` — Atomic split accounting: principal paid posts as `FinancialTransfer` reducing `loan_liability` (not expense); interest paid posts as `Loan Interest` expense in double-entry ledger & Phase 4 analytics.

---

## 7. Document Management & Local OCR (`/api/v1/documents` — Phase 7)

- `POST /api/v1/documents/upload` (`201`) — Rate-limited multipart upload (PDF, PNG, JPG, JPEG, WebP), magic-byte validation, SHA-256 duplicate detection, opaque UUID storage, and async OCR queueing.
- `GET /api/v1/documents`, `/overview`, `/processing-history` — Overview metrics, searchable/filterable paginated library, and job status/retry history.
- `GET /api/v1/documents/{document_id}`, `DELETE /api/v1/documents/{document_id}` — Detailed metadata + extraction + audit trail; deletion cleans DB and private disk file.
- `GET /api/v1/documents/{document_id}/download`, `/preview?page=N` — Authenticated private download & page-rendered PNG preview with `X-Content-Type-Options: nosniff`.
- `POST /api/v1/documents/{document_id}/process`, `GET /processing-status` — Re-queue failed/pending OCR jobs and poll job status.
- `GET /api/v1/documents/{document_id}/extraction`, `PATCH /extraction` — View immutable raw OCR evidence & structured fields; save human edits and per-field `accepted`/`rejected` decisions cleanly.
- `POST /api/v1/documents/{document_id}/confirm`, `/reject`, `/link` — Human confirmation workflow creating unpaid bills (`BillService`), ledger transactions (`TransactionService`), or linking existing Phase 2–6 records atomically.

---

## 8. Gmail OAuth Ingestion & SMS Boundary (`/api/v1/email` — Phase 7)

- `GET /api/v1/email/connections`, `GET /gmail/connect`, `GET /gmail/callback`, `POST /gmail/disconnect` — Read-only (`gmail.readonly`) Google OAuth 2.0 connection lifecycle with HMAC-SHA256 state verification & Fernet token encryption at rest.
- `POST /api/v1/email/gmail/sync`, `GET /sync-history` — Incremental `historyId` / query financial sync producing private attachments and reviewable candidates.
- `GET /api/v1/email/candidates`, `GET /candidates/{id}`, `POST /candidates/{id}/confirm`, `/reject` — Review, duplicate-warning inspection, confirmation, and rejection workflows.
- `GET /api/v1/email/sms/status` — Explicit SMS ingestion availability boundary (`available: false` in web SaaS without native Android companion).


## Phase 8 — AI Expense Intelligence (`/api/v1/intelligence`)

All endpoints require an authenticated session (`get_current_user`); mutating `POST`/`PATCH` routes require `verify_csrf` (`X-CSRF-Token`) and enforce strict `user_id` isolation.

- `GET /api/v1/intelligence/overview` — Returns aggregate coverage metrics, personal ML model status & evaluation scores, recent `AiProcessingJob` runs, top expense categories (`180d`), top open anomalies, and unread insights.
- `POST /api/v1/intelligence/run` — Runs the full Phase 8 intelligence pipeline (`ML training -> layered categorization & merchant normalization -> recurring detection -> pattern aggregation -> statistical anomaly detection -> insights`). Supports `async_job: true` to enqueue a PostgreSQL `AiProcessingJob`.
- `POST /api/v1/intelligence/categorize` — Executes layered transaction categorization (`user_override -> confirmed_mapping -> deterministic_rule -> ml_classifier -> optional groq llm_fallback -> fallback`).
- `GET /api/v1/intelligence/categorizations` — Paginated, searchable transaction categorization suggestions with confidence, method, explanation, and review status (`needs_review`, `auto_categorized`, `confirmed`, `overridden`, `dismissed`).
- `POST /api/v1/intelligence/categorizations/{transaction_id}/override` — Confirms, overrides, or dismisses a category suggestion; records `CategorizationFeedback`; updates `FinancialTransaction.category_id` only on explicit user `confirm`/`override` and optionally saves an authoritative `MerchantCategoryMapping`.
- `GET /api/v1/intelligence/feedback` — Lists recent user categorization feedback events.
- `POST /api/v1/intelligence/ml/train` & `GET /api/v1/intelligence/ml/status` — Trains/inspects the strict per-user `TF-IDF + LogisticRegression` classifier and reports honest `insufficient_data` when fewer than 12 eligible samples across 2+ classes exist.
- `GET /api/v1/intelligence/merchants` & `PATCH /api/v1/intelligence/merchants/{merchant_id}` — Lists canonical normalized merchants with raw aliases (`MerchantAlias`) and lets users confirm/rename display names and bind authoritative default categories.
- `GET /api/v1/intelligence/recurring-candidates` & `POST /api/v1/intelligence/recurring-candidates/{candidate_id}/decision` — Lists fixed & variable recurring candidates and confirms, rejects, or links/creates a real Phase 6 `Subscription`.
- `GET /api/v1/intelligence/patterns` — Returns deterministic `Decimal` spending patterns (essential/discretionary, fixed/variable, recurring/non-recurring, weekend/weekday, merchant concentration, monthly/weekly/day-of-week trends), excluding transfers and reversed journals.
- `GET /api/v1/intelligence/anomalies` & `POST /api/v1/intelligence/anomalies/{anomaly_id}/review` — Lists statistical baseline deviations (`robust_median_mad`, `monthly_baseline_comparison`, `recurring_charge_delta`) and supports `acknowledge` / `dismiss` / `reopen`.
- `GET /api/v1/intelligence/insights` & `POST /api/v1/intelligence/insights/{insight_id}/review` — Lists evidence-backed insights (`new` / `read` / `dismissed`) and supports `mark_read` / `dismiss` / `reopen`.
- `GET /api/v1/intelligence/jobs` — Lists recent `AiProcessingJob` execution records.
