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
