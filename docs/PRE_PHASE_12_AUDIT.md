# Pre-Phase 12 Repository Audit — Settings & Integrations Center

**Audit Date:** 2026-11-26  
**Branch:** `feature/phase-6-subscriptions-loans`  
**Starting Commit:** `f06aee5` (`f06aee5fa3b2ed8976ab81a41a83bd936576f62f`)  
**Alembic Head:** `c87faa90fd29`  
**Working Tree Protection:** Untracked `hdfc_oct_2026_statement.csv`, `.env`, and `backend/.env` preserved untouched.

---

## 1. Existing Modules Inspected & Functional Status

| Phase | Existing Backend Assets | Existing Frontend Assets | Reusability & Status |
|---|---|---|---|
| **1 — Auth, Users & Sessions** | `User`, `UserSession`, `UserPreference` (`preferred_currency`, `locale`, `timezone`, `date_format`, `notification_preferences` JSON), `routes/auth.py` (`/sessions`, `/logout`, `/logout-all`, `/sessions/{id}`), `routes/users.py` (`/me`, `/me/preferences`) | `ProfilePage.tsx`, `PreferencesPage.tsx`, `SessionsPage.tsx`, `AuthContext.tsx`, `authApi.ts` | **Functional & Reused.** Missing: authenticated `POST /api/v1/auth/change-password`, structured privacy/data summary endpoint, unified tabbed `SettingsPage.tsx`, expanded notification/app preference keys, and active sidebar link for `Settings`. |
| **2 & 3 — Banking & Imports** | `BankingConnection`, `BankingSyncRun`, `routes/banking/connections.py`, `BankingService` (demo bank institutions + consent + idempotent sync), CSV/XLSX `routes/imports.py` | `BankingPage.tsx`, `ImportsPage.tsx`, `financeApi.ts`, `importsApi.ts` | **Functional & Reused.** Simulated demo banking is active; real Open Banking / Account Aggregator (AA) is **not implemented** and must be surfaced honestly as unavailable/planned. |
| **5 & 6 — Bills, Subscriptions, Loans & Reminders** | `BillReminder`, `Notification`, `ReminderService` (`email_reminders_enabled`, `sms_reminders_enabled`, `phone_number`), `SmsService` (Webhook SMS with Phase 11 SSRF guard), `EmailService` (SMTP adapter) | `BillsPage.tsx`, `SubscriptionsPage.tsx`, `LoansPage.tsx`, `AppShell.tsx` notification bell | **Functional & Reused.** Granular reminder toggles (`subscription_reminders`, `loan_emi_reminders`, `payment_due_reminders`, insights/anomalies/forecasts) should persist cleanly in `UserPreference.notification_preferences` and be respected without modifying underlying financial obligations. |
| **7 — Documents, Local OCR, Gmail & SMS Ingestion** | `FinancialDocument`, `EmailConnection` (Fernet encrypted access/refresh tokens), `EmailSyncHistory`, `routes/email.py` (`/connections`, `/gmail/connect`, `/gmail/callback`, `/gmail/disconnect`, `/gmail/sync`, `/sms/status`), `UnavailableSmsIngestionProvider` | `DocumentsPage.tsx`, `OcrReviewModal.tsx`, `documentsApi.ts` | **Functional & Reused.** Gmail OAuth + encrypted storage are real and reusable directly; incoming Android SMS ingestion is **honestly unavailable** in web SaaS (`SMS_INGESTION_ENABLED=false`). |
| **8 & 9 — AI Expense Intelligence & Forecasting** | `AiProcessingJob`, `GroqAiProvider`, `GROQ_ENABLED`, `GROQ_MODEL`, `ForecastScenario` | `IntelligencePage.tsx`, `ForecastingPage.tsx` | **Functional & Reused.** Groq config is server-side only; no secret key exposure. Needs a real non-mutating connectivity check & status card in Integrations Center. |
| **10 — AI Assistant, RAG & Web Research** | `UserAiPreference` (`default_web_provider`, `web_search_enabled`, `voice_read_aloud_enabled`, `auto_execute_actions`), `LangSearchProvider`, `FirecrawlProvider`, `TavilyProvider`, `WebResearchService` (no-silent-fallback), `routes/assistant.py` | `AssistantPage.tsx`, `assistantApi.ts`, `types/assistant.ts` | **Functional & Reused.** Preference persistence and explicit provider attribution already exist in PostgreSQL and must be surfaced & synced from both Integrations and Settings without duplication. |
| **11 — Production Security & Infrastructure** | Valkey hybrid rate limiter (`rate_limit.py`), HTTP security headers, `TrustedHostMiddleware`, OpenAPI production suppression, `SMS_WEBHOOK_URL` SSRF guard, stale `AiProcessingJob` recovery | Production build verified (`vite build`) | **Preserved cleanly.** All new endpoints will enforce `get_current_user`, `verify_csrf` on mutations, ownership scoping, rate limiting, and zero credential leaks. |

---

## 2. Database Migration Assessment

**Conclusion:** **No Alembic migration or new database table is required.**

- `user_preferences` already provides structured localization columns (`preferred_currency`, `locale`, `timezone`, `date_format`) plus the extensible JSON `notification_preferences` column (storing granular alert toggles, localization extensions like `week_start`/`number_format`/`language`, and functional app preferences like `default_landing_view` and `compact_sidebar`).
- `user_ai_preferences` already stores `default_web_provider`, `web_search_enabled`, `voice_read_aloud_enabled`, and `auto_execute_actions`.
- `email_connections`, `email_sync_history`, `banking_connections`, `banking_sync_runs`, `ai_processing_jobs`, and `ai_messages` already record real connection states, sync timestamps, and provider error history in PostgreSQL.

Preserving the existing single linear Alembic head `c87faa90fd29` satisfies the strict constraint against unnecessary database tables while maintaining PostgreSQL as the single source of truth.

---

## 3. Gaps Identified for Implementation

1. **Integrations Backend Orchestration (`/api/v1/integrations/*`):** Add unified aggregation and real live health/connectivity checks (`overview`, `providers`, `providers/{id}`, `providers/{id}/test`, `connections`, `connections/{id}/disconnect`) reusing existing banking, Gmail, SMS, Groq, LangSearch/Firecrawl/Tavily, and SMTP adapters without duplicating OAuth/sync routes.
2. **Authenticated Password Change (`POST /api/v1/auth/change-password`):** Enable verified Argon2id password rotation inside Settings -> Security with optional revocation of all other active sessions (`SessionRepository.revoke_all_for_user(..., except_session_id=...)`).
3. **Extended Notification, Localization & App Preferences + Privacy Summary (`/api/v1/users/me/privacy-summary`):** Normalize and persist notification toggles (`bill_reminders`, `subscription_reminders`, `loan_emi_reminders`, `payment_due_reminders`, `financial_insights`, `spending_anomalies`, `forecast_notifications`, `email_alerts`, `email_reminders_enabled`), formatting (`week_start`, `number_format`, `language`), and functional UI preferences (`default_landing_view`, `compact_sidebar`), plus expose real per-user record counts for Privacy & Data Management.
4. **Integrations Frontend Center (`IntegrationsPage.tsx`) & Settings Center (`SettingsPage.tsx`):** Build full, accessible, responsive pages and activate `Integrations` and `Settings` in [AppShell.tsx](file:///home/ckirankumar/Finance%20AI/frontend/src/layouts/AppShell.tsx) and [App.tsx](file:///home/ckirankumar/Finance%20AI/frontend/src/app/App.tsx).
