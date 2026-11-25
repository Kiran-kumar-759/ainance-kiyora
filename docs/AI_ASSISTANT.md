# AI Personal Finance Assistant (Phase 10)

## Overview
Phase 10 adds a persistent, explainable **AI Personal Finance Assistant** to the existing India-first AI Personal Finance Manager modular monolith (`FastAPI` + `PostgreSQL` + `React/TypeScript`).

It integrates:
1. **Persistent Multi-Turn Conversations:** Conversations (`ai_conversations`), messages (`ai_messages`), and user AI preferences (`user_ai_preferences`) are stored in PostgreSQL and strictly isolated per `user_id`.
2. **Controlled Read-Only Personal Finance Tools (`backend/app/services/assistant/finance_tools.py`):**
   - `get_account_balances` — active accounts, liquid assets, liabilities, and net worth (`Decimal` INR).
   - `get_spending_summary` — 30-day income, expense, net cash flow, and top expense categories (respecting transfer/reversal exclusions and `Asia/Kolkata` timezone).
   - `get_upcoming_commitments` — active/overdue bills, recurring subscriptions, and loan EMIs.
   - `get_forecast_and_insights` — latest Phase 8 anomalies/insights and Phase 9 cashflow forecast summary.
   - **Zero write tools exist for the LLM:** assistant prompts can never create, alter, or delete transactions, transfers, bills, loans, or subscriptions.
3. **Groq Orchestration + Deterministic Fallback (`backend/app/services/assistant/assistant_orchestrator.py`):**
   - Uses `GroqAiProvider` server-side when `GROQ_ENABLED=true` and `GROQ_API_KEY` is configured.
   - Falls back to a transparent deterministic evidence-backed response when Groq is unavailable or disabled.
   - Post-processes inline citations (`[N]`) and strips any fabricated/out-of-range citation numbers.
