# AI Expense Intelligence Overview (Phase 8)

Phase 8 extends the modular monolith with an explainable, PostgreSQL-backed expense intelligence system in `backend/app/services/ai/`, exposed via `/api/v1/intelligence/*` and surfaced in the `AI Insights` workspace (`frontend/src/pages/intelligence/IntelligencePage.tsx`).

## Core Design Principles
- **PostgreSQL & Ledger Safety:** AI services never mutate `LedgerJournal`, `LedgerEntry`, account balances, bills, or loans. `FinancialTransaction.category_id` is modified only upon explicit user `confirm` or `override`.
- **Transfer & Reversal Exclusions:** Reuses Phase 4 active-journal filtering (`LedgerJournal.is_reversed`) and excludes `transfer_id` legs so self-transfers and credit card repayments never inflate expense figures.
- **Provider-Independent AI Boundary:** `AiProvider` (`NullAiProvider`, `GroqAiProvider`) is strictly optional (`GROQ_ENABLED=false` default). Account numbers, card numbers, phone numbers, emails, and UPI VPAs are redacted before any external AI call, and LLM JSON outputs are strictly validated via Pydantic against the user's allowed categories.
- **Strict User Isolation:** Every database table, query, merchant identity, feedback log, anomaly, insight, and `TF-IDF + LogisticRegression` model is scoped strictly to `user_id`.
