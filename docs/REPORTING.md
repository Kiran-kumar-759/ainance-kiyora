# Financial Reporting & Secure CSV Export (Phase 4)

**Project:** AI Personal Finance Manager — India  
**Modules:** `backend/app/services/analytics/report_service.py`, `backend/app/api/routes/reports.py`, `frontend/src/pages/reports/ReportsPage.tsx`

---

## 1. Available Reports

1. **Monthly Financial Summary** (`GET /api/v1/reports/summary`)
2. **Income Report** (`GET /api/v1/reports/income`)
3. **Expense Report** (`GET /api/v1/reports/expenses`)
4. **Category-Wise Spending Report** (`GET /api/v1/reports/categories`)
5. **Account-Wise Activity Report** (`GET /api/v1/reports/accounts`)
6. **Cash-Flow Report** (`GET /api/v1/reports/cashflow`)
7. **Savings Report** (`GET /api/v1/reports/savings`)
8. **Transaction Summary Report** (`GET /api/v1/reports/transactions`)
9. **Report Catalog** (`GET /api/v1/reports`)

---

## 2. Filtering & Contents

Every report endpoint accepts consistent query parameters:
- `period` (preset) OR `start_date` + `end_date` (`YYYY-MM-DD`)
- `account_id` (UUID, verified owned by authenticated user)
- `transaction_type` (`income`, `expense`, `transfer`)
- `category_id` (UUID, verified owned/visible to authenticated user)
- `source` (`manual`, `csv_import`, `xlsx_import`, `demo_bank`)

Each JSON report returns:
- Metadata: report title, formatted start/end dates, IST `generated_at`, `currency = "INR"`, active filters.
- Summary metrics (`Total Income`, `Total Expenses`, `Net Savings`, `Savings Rate`).
- Category breakdown & account breakdown tables.
- Time-series cashflow array.
- Detailed matching transactions & calculation traceability metadata.

---

## 3. CSV Export Format & Security (`GET /api/v1/reports/export/csv`)

- **Encoding & Headers:** Streams `text/csv; charset=utf-8` with `Content-Disposition: attachment; filename="pfm_<report_type>_<YYYYMMDD>_<YYYYMMDD>.csv"` and `X-Content-Type-Options: nosniff`.
- **Indian Conventions:**
  - Transaction dates formatted strictly as `DD/MM/YYYY`.
  - Amounts rendered as exact 2-decimal INR figures (e.g., `1500.50`).
- **Formula Injection Defense (`sanitize_csv_cell`):**
  - Any text cell whose stripped value starts with `=`, `+`, `-`, `@`, `\t`, or `\r` is automatically escaped with a leading single quote (`'`) so spreadsheet software treats it strictly as literal text.
- **Tenant Isolation:** Export re-runs `generate_report` under `get_current_user` and ownership checks, ensuring users can only export their own authorized financial data.
- **Print Support:** `ReportsPage.tsx` includes clean print styling (`print:hidden` around filter chrome) and browser print triggering via `window.print()`.
