# Financial Forecasting & Predictive Analytics (Phase 9)

Phase 9 adds a deterministic, PostgreSQL-backed predictive analytics and financial forecasting engine in `backend/app/services/forecasting/`, exposed via `/api/v1/forecasting/*` and rendered in the **Forecasting** workspace (`frontend/src/pages/forecasting/ForecastingPage.tsx`).

## Core Accounting & Isolation Guarantees
- **Read-Only Financial Projection:** Generating forecasts, cash-flow trajectories, risk warnings, savings estimates, backtests, or what-if scenarios NEVER creates confirmed transactions, ledger journals, bills, subscriptions, or balance modifications.
- **Ledger Semantics Preserved:** Reuses active-journal (`LedgerJournal.is_reversed`) and `transfer_id IS NULL` filters so internal transfers, credit card bill transfers, loan principal repayments, and reversed entries are excluded cleanly. Loan EMIs preserve principal/interest splits and liabilities (`credit_card`, `loan_liability`) remain separated from liquid bank balances.
- **No Fabricated Numbers:** Users with `< 3` expenses or `< 14` days history receive explicit `insufficient_data` statuses. Variable bills without amounts retain `expected_amount: null` (`amount_certainty = "unknown_amount"`). Unconfirmed Phase 8 `RecurringPaymentCandidate` rows (`review_status = "pending"`) are labeled explicitly as unconfirmed and excluded from confirmed obligation totals.
- **Tenant & AI Boundaries:** Strictly isolated per `user_id`. Phase 9 requires zero external LLM/Groq calls or network APIs.
