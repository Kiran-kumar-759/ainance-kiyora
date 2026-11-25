# Phase 6 Module B — Loan & EMI Management

## 1. Overview & Existing-Loan First Design

Implemented across `backend/app/models/loans.py`, `backend/app/services/loans/loan_service.py`, and `backend/app/api/routes/loans.py`:

- Supports `personal`, `education`, `home`, `vehicle`, `gold`, `business`, `consumer_durable`, and `other` loans.
- Supports **both newly started loans and already-existing mid-tenure loans** (`outstanding_principal`, optional `original_principal`, `remaining_tenure_months`, optional `original_tenure_months`, optional user-verified `emi_amount`). Never assumes a loan is brand-new and never guesses outstanding principal from EMI transactions.

## 2. Double-Entry Ledger Integration & Zero Analytics Double Counting

Every `Loan` creates a dedicated `FinancialAccount` with `account_type = "loan_liability"` (`source = "loan"`):

1. **Liability Valuation:** `LedgerRepository.calculate_account_balance` computes `Total Credits - Total Debits` for `{"credit_card", "loan_liability"}`. `AccountService.get_summary`, `DashboardService`, and `AnalyticsService` include active `loan_liability` balances in Liabilities and Net Position (`Assets - Liabilities`).
2. **Optional Disbursement Recognition:** When registering a brand-new loan with `record_disbursement_to_account_id`, a balanced `FinancialTransfer` moves funds from `loan_liability` (Credit increases liability) to the bank asset account (Debit increases cash) — **never** misclassified as earned income.
3. **Split EMI Accounting (`Principal + Interest + Optional Fee`):**
   - **Principal Paid (`₹12,000`):** Posted as a balanced `FinancialTransfer` from the repayment bank account (Credit decreases cash) to `loan_liability` (Debit decreases loan liability). Because `transfer_id IS NOT NULL` (`transaction_type = "transfer"`), **Phase 4 Analytics (`AnalyticsRepository`) never counts principal repayment as an expense**.
   - **Interest Paid (`₹3,000`):** Posted via `TransactionService.create_transaction(..., transaction_type="expense", category_id="Loan Interest", source="loan_payment", commit=False)` — **counted accurately as actual expense** while total cash outflow is `₹15,000`.
   - **Optional User Fee:** Posted separately as an explicit fee expense only when provided by the user.
4. **Reversals & Corrections:** `POST /api/v1/loans/{loan_id}/payments/{payment_id}/reverse` reverses the transfer and expense journals atomically via `LedgerService`, restoring bank cash, loan liability balance, and installment state cleanly.

## 3. Floating Rate Revisions, Prepayment Scenarios & Shared Reminders

- **Rate Revisions (`/rate-revision`):** Records `LoanInterestRateHistory`, preserves all historical `paid`/`partially_paid` installments unchanged, cancels future unpaid rows, and regenerates remaining installments under `recalculate_emi` or `adjust_tenure`.
- **Prepayment Simulator (`/prepayment-scenario`):** Runs pure read-only `Decimal` simulations (`is_scenario_simulation = True`) without modifying PostgreSQL rows or ledger balances; users explicitly confirm real prepayments/foreclosures via `/payments`.
- **Reminders:** Uses Phase 5 `BillReminder` (`reminder_scope = "loan_emi"`) and `Notification` infrastructure (`FOR UPDATE SKIP LOCKED`), automatically cancelling pending reminders when a loan closes or is archived.
