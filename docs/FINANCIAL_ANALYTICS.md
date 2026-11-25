# Financial Analytics Architecture (Phase 4)

**Project:** AI Personal Finance Manager — India  
**Modules:** `backend/app/schemas/analytics/`, `backend/app/repositories/analytics/`, `backend/app/services/analytics/`, `backend/app/api/routes/analytics.py`  
**Frontend:** `frontend/src/pages/finance/DashboardPage.tsx`, `frontend/src/pages/analytics/AnalyticsPage.tsx`, `frontend/src/components/charts/FinanceCharts.tsx`

---

## 1. Architecture Layers

1. **API Routes (`backend/app/api/routes/analytics.py`)**:
   - All routes enforce authenticated access via `Depends(get_current_user)` and strict `user_id` ownership checks.
   - Read-only `GET` endpoints validate date ranges, periods, granularities, and account/category filters cleanly (`400` on invalid range/period, `404` on unowned account/category).
2. **Analytics Repository (`backend/app/repositories/analytics/analytics_repository.py`)**:
   - Executes single-query PostgreSQL `GROUP BY`, `SUM`, `COUNT`, and `date_trunc` aggregations rather than loading raw transaction tables into Python.
   - Enforces active account isolation (`FinancialAccount.status != "disconnected"`), transfer exclusion (`transfer_id IS NULL` and `transaction_type IN ('income', 'expense')`), and reversed-journal exclusion.
3. **Analytics Service (`backend/app/services/analytics/analytics_service.py` & `period_utils.py`)**:
   - Interprets calendar boundaries strictly in `Asia/Kolkata` (`ZoneInfo("Asia/Kolkata")`).
   - Orchestrates dashboard summaries, cash-flow series, category shares, source breakdowns (`manual`, `csv_import`, `xlsx_import`, `demo_bank`), period-over-period comparisons, account-wise activity, and ledger-reconstructed balance history.
4. **Frontend Visualization Layer**:
   - Displays backend-calculated INR `Decimal` values using `en-IN` formatting (`formatINR`) and `DD/MM/YYYY` formatting (`formatDate`).
   - Provides custom responsive SVG charts (grouped bar, trend line, category donut, horizontal comparison bars, account distribution, period comparison) with interactive tooltips and 1-click drill-down into filtered `/transactions`.

---

## 2. API Endpoints (`/api/v1/analytics`)

| Endpoint | Description |
|---|---|
| `GET /api/v1/analytics/dashboard` | Real-time balance sheet + period cash flow, comparisons, category breakdown, 6M trend, account balances & recent transactions |
| `GET /api/v1/analytics/income` | Income totals, comparison vs previous period, category/account/source splits & trend |
| `GET /api/v1/analytics/expenses` | Expense totals, daily/monthly averages, category/account/source splits, largest expenses & trend |
| `GET /api/v1/analytics/cashflow` | Inflows, outflows, net cash flow, savings rate & bucketed time series |
| `GET /api/v1/analytics/categories` | Ranked spending or income categories with shares, counts & average ticket size |
| `GET /api/v1/analytics/trends` | Period trends, top 4 category series & ledger-reconstructed balance history |
| `GET /api/v1/analytics/comparisons` | Month/quarter/year/3-month/custom comparison engine with partial-period warnings |
| `GET /api/v1/analytics/accounts` | All active accounts with authoritative balances & period inflows/outflows |
| `GET /api/v1/analytics/accounts/{account_id}` | Deep-dive analytics, trend, category distribution & recent transactions for one account |

*(Legacy `GET /api/v1/finance/dashboard` remains preserved and delegates to `period_utils` & `AnalyticsRepository` for consistency.)*

---

## 3. Query Performance & Limitations

- Relies on composite indexes already present on `financial_transactions`:
  - `ix_financial_transactions_user_date` `(user_id, transaction_date)`
  - `ix_financial_transactions_user_account_date` `(user_id, account_id, transaction_date)`
- Bucketed time-series queries use PostgreSQL `date_trunc` grouped by interval and `transaction_type`.
- **Historical Balances:** The system does not maintain artificial historical balance snapshot tables. Instead, `TrendAnalyticsResponse.balance_history` reconstructs balances chronologically from unreversed `LedgerEntry` + `LedgerJournal` rows (`is_reversed = FALSE`). Opening balances apply from their recorded ledger `entry_date`.
- **Known Scope Boundaries (Deferred to Future Phases):** AI/LLM categorization & explanations, forecasting/anomaly detection, PDF bank statement ingestion, and Redis caching (not required at current scale).
