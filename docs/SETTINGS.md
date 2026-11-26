# Settings Center Architecture & Persistence Guide

**Module Scope:** Pre-Phase 12 Completion (`frontend/src/pages/settings/SettingsPage.tsx`, `backend/app/api/routes/users.py`, `backend/app/api/routes/auth.py`, `backend/app/services/user_service.py`)

---

## 1. Settings Sections Implemented

1. **Profile & Account:** Updates display name (`PATCH /api/v1/users/me`), displays verified/pending email state + resend verification action, account timestamps, and onboarding wizard link.
2. **Security & Sessions:** Authenticated password rotation (`POST /api/v1/auth/change-password`) using Argon2id verification (`current_password` + `new_password`) and optional invalidation of all other active sessions (`SessionRepository.revoke_all_for_user(..., except_session_id=...)`), plus active device inspection and single/all revocation (`GET /api/v1/auth/sessions`, `DELETE /api/v1/auth/sessions/{id}`, `POST /api/v1/auth/logout-all`). Zero plaintext tokens or password hashes are ever exposed.
3. **Localization & Formatting:** Persists `preferred_currency` (`INR` default), `locale` (`en-IN` Lakhs/Crores default), `timezone` (`Asia/Kolkata` default), `date_format` (`DD/MM/YYYY`), `week_start`, and supported language (`en-IN`) inside PostgreSQL `user_preferences`. Changing formatting preferences never alters historical transaction ledger amounts or currencies.
4. **Notifications & Reminders:** Persists granular switches (`bill_reminders`, `subscription_reminders`, `loan_emi_reminders`, `payment_due_reminders`, `financial_insights`, `spending_anomalies`, `forecast_notifications`, `monthly_summary`, `email_alerts`, `email_reminders_enabled`, `sms_reminders_enabled`, `phone_number`) inside `user_preferences.notification_preferences` with merge semantics. `ReminderService` skips muted categories cleanly without deleting underlying commitments, and UI shows live SMTP transport status separately.
5. **AI Assistant & Web Research:** Reads and persists `user_ai_preferences` (`default_web_provider`, `web_search_enabled`, `voice_read_aloud_enabled`, `auto_execute_actions`) via `/api/v1/assistant/preferences` with zero duplicate storage.
6. **Privacy & Data Management:** Calls `GET /api/v1/users/me/privacy-summary` for live PostgreSQL per-user counts, storage/OAuth/AI/search disclosures, link to Documents management, formula-safe CSV export triggers (`/api/v1/reports/*.csv`), and explicit explanation that destructive self-service account deletion is deferred until full multi-module archive & cascade verification.
7. **Application Preferences:** Persists genuine workspace controls (`default_landing_view` and `compact_sidebar`) respected by `App.tsx` and `AppShell.tsx`.

---

## 2. Database Schema Reuse

All settings persist in PostgreSQL reusing `users`, `user_sessions`, `user_preferences`, and `user_ai_preferences` at Alembic head `c87faa90fd29`, requiring zero additional tables or redundant migrations.
