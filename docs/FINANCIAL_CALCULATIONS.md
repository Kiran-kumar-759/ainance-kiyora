# Financial Calculation Methodology & Accounting Rules

**Project:** AI Personal Finance Manager — India  
**Authoritative Engine:** Double-Entry Ledger (`LedgerRepository` / `LedgerService`) + `AnalyticsRepository`  

---

## 1. Monetary Precision

- All monetary persistence uses PostgreSQL `NUMERIC(19, 2)`.
- All backend arithmetic uses Python `Decimal` quantized to `0.01` with `ROUND_HALF_UP`.
- No Python `float` or JavaScript floating-point math is used as the financial authority.

---

## 2. Balance Sheet Positions (Real-Time Ledger)

Account balances reflect real-time state from `LedgerRepository.calculate_account_balance` across active (`status == 'active'`) accounts:

- **Asset Accounts** (`savings`, `current`, `cash`, `digital_wallet`, `other`):
  $$\text{Balance} = \sum \text{Debits} - \sum \text{Credits}$$
- **Liability Accounts** (`credit_card`):
  $$\text{Outstanding Liability} = \sum \text{Credits} - \sum \text{Debits}$$
- **Total Assets:** Sum of balances of all active non-credit-card accounts.
- **Total Liabilities:** Sum of outstanding liabilities of all active `credit_card` accounts.
- **Net Financial Position:**
  $$\text{Net Financial Position} = \text{Total Assets} - \text{Total Liabilities}$$

*(Account balances represent real-time positions and do not change when switching transaction date-range filters; the UI explicitly surfaces this distinction.)*

---

## 3. Period Income, Expenses, Net Savings & Savings Rate

- **Income (`Total Income`):** $\sum \text{amount}$ where `transaction_type = 'income'`, `transfer_id IS NULL`, account status is not `'disconnected'`, and transaction has no solely-reversed journal.
- **Expenses (`Total Expenses`):** $\sum \text{amount}$ where `transaction_type = 'expense'`, `transfer_id IS NULL`, account status is not `'disconnected'`, and transaction has no solely-reversed journal.
- **Net Savings / Net Cash Flow:**
  $$\text{Net Savings} = \text{Total Income} - \text{Total Expenses}$$
- **Savings Rate (%):**
  - When $\text{Total Income} > 0$: $\left(\frac{\text{Net Savings}}{\text{Total Income}}\right) \times 100$ rounded to 2 decimal places.
  - When $\text{Total Income} \le 0$: returns `null` (`N/A (Zero Income)` in UI) — division by zero is impossible.

---

## 4. Transfers, Credit Cards, Reversals & Statement Imports

- **Transfers Excluded:** Inter-account transfers create paired `FinancialTransaction` legs (`transaction_type = 'transfer'`, non-null `transfer_id`). Both legs are strictly excluded from Income and Expense sums.
- **Credit Card Semantics:**
  - Card purchases (`expense` on `credit_card`) increase card liability AND count toward period expenses.
  - Card bill payments (`transfer` from asset account to `credit_card`) decrease asset balance and reduce card liability, and are **excluded from period expenses** so spending is never double-counted.
  - Card refunds/credits (`income` on `credit_card`) reduce card liability cleanly.
- **Reversals & Edits:**
  - When a transfer is reversed (`FinancialTransfer.status = 'reversed'`, `LedgerJournal.is_reversed = TRUE`), its legs remain excluded.
  - When `TransactionService.update_transaction` modifies amount/date, the old journal is marked `is_reversed = TRUE` and a fresh active journal (`is_reversed = FALSE`) is posted with the same `transaction_id`. Our SQL predicate (`NOT (has_reversed_journal AND NOT has_active_journal)`) preserves edited transactions while excluding truly reversed ones.
- **CSV/XLSX Statement Imports:** Only committed transactions persisted into `financial_transactions` are counted. Uncommitted `import_batches` / `import_rows` (`mapping_required`, `ready_for_review`, `invalid`, `duplicate`, `potential_duplicate`, `excluded`) are never included in analytics.

---

## 5. Indian Timezone & Period Boundaries

All preset periods resolve against `Asia/Kolkata` calendar dates (`ist_today()`):
- `this_week`: Monday to Sunday of the current ISO week (`is_partial_period` flagged if today < Sunday).
- `this_month` / `last_month`: 1st to last calendar day of the respective month.
- `this_quarter` / `last_quarter`: Standard Q1 (Jan–Mar), Q2 (Apr–Jun), Q3 (Jul–Sep), Q4 (Oct–Dec).
- `this_year` / `last_year`: Jan 1 to Dec 31.
- `last_3_months` / `last_6_months`: Full calendar months including current month.
- `all_time`: Earliest unreversed transaction date through today.
- `custom`: Inclusive `[start_date, end_date]` (`400` if `start_date > end_date`).

---

## 6. Period-over-Period Comparison Logic

$$\text{Difference} = \text{Current} - \text{Previous}$$
$$\text{Change \%} = \begin{cases} \text{null} & \text{if } \text{Previous} = 0 \\ \frac{\text{Difference}}{|\text{Previous}|} \times 100 & \text{otherwise} \end{cases}$$

When comparing an in-progress current period (`is_partial_period = True`) against a completed previous period (`is_partial_period = False`), `PeriodComparisonResponse.partial_period_warning` explicitly displays elapsed days vs total days so users are never misled by apples-to-oranges totals.
