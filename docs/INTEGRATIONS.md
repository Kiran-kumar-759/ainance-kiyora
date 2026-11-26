# Integrations Center Architecture & Operations Guide

**Module Scope:** Pre-Phase 12 Completion (`frontend/src/pages/integrations/IntegrationsPage.tsx`, `backend/app/api/routes/integrations.py`, `backend/app/services/integrations/integration_service.py`)

---

## 1. Overview

The Integrations Center provides a live, PostgreSQL-backed control plane over external and simulated integrations across Phases 2–10 without fabricating connection states or exposing server credentials.

### Supported & Planned Integrations
| Provider ID | Category | Real Status Model | Backend Reused |
|---|---|---|---|
| `demo_banking` | Banking | Simulated (`connected` / `available`) | `BankingService`, `BankingConnection`, `BankingSyncRun` |
| `account_aggregator` | Banking | `planned` / `unavailable` (explicitly NOT fabricated) | Future RBI Account Aggregator placeholder disclosure |
| `gmail` | Email (OAuth) | `connected` / `configured_not_connected` / `error` / `unavailable` | `EmailIngestionService`, `EmailConnection` (Fernet-encrypted tokens) |
| `sms_outgoing` | SMS Reminders | `connected` / `error` / `unavailable` | `SmsService` (`SMS_WEBHOOK_URL` validated via `is_safe_public_url`) |
| `sms_ingestion` | SMS Ingestion | `unavailable` (browser SaaS limitation documented honestly) | `UnavailableSmsIngestionProvider` |
| `groq` | AI Provider | `connected` / `configured_not_connected` / `error` / `unavailable` | `GroqAiProvider`, `AiProcessingJob`, `AiMessage` |
| `tavily`, `langsearch`, `firecrawl` | Web Research | `available` / `error` / `unavailable` (`is_preferred` from `user_ai_preferences`) | `WebResearchService`, Phase 10 registry (no silent fallback) |
| `smtp` | Notifications | `connected` / `unavailable` | `EmailService` / `smtplib.SMTP` NOOP handshake |

---

## 2. Backend APIs (`/api/v1/integrations/*`)

All endpoints require HttpOnly cookie authentication (`get_current_user`); mutations enforce `verify_csrf`.

- `GET /api/v1/integrations/overview`: Accurate counts (`total_integrations`, `configured_count`, `connected_count`, `unavailable_count`, `attention_required_count`, `planned_count`) excluding planned integrations from connected counts.
- `GET /api/v1/integrations/providers` & `GET /api/v1/integrations/providers/{provider_id}`: Safe metadata, capabilities, and required environment variable names (zero secrets).
- `POST /api/v1/integrations/providers/{provider_id}/test`: Rate-limited (`10/min` per user) non-mutating provider health check. Web research tests use the exact requested provider without silent fallback.
- `GET /api/v1/integrations/connections` & `GET /api/v1/integrations/connections/{connection_id}`: Tenant-owned Banking & Gmail OAuth connections (`404` on foreign ownership).
- `POST /api/v1/integrations/connections/{connection_id}/disconnect`: Revokes Banking or Gmail OAuth grant while preserving imported accounts, transactions, bills, and uploaded documents.

---

## 3. Web Research Provider Selection & Assistant Link

Selecting a preferred provider (`langsearch`, `firecrawl`, or `tavily`) on the Integrations page persists cleanly via `PATCH /api/v1/assistant/preferences` (`user_ai_preferences.default_web_provider`) and is respected directly by Phase 10 AI Assistant turns with explicit `provider_used` attribution and zero silent fallback.
