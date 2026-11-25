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
