# Phase 11 Security Audit Report

**Project:** AI Personal Finance Manager — India  
**Branch:** `feature/phase-6-subscriptions-loans`  
**Audit Date:** 2026-11-25  

---

## 1. Threat Model & Verification Summary

| Security Control Domain | Implementation Inspected | Phase 11 Status & Hardening |
|---|---|---|
| **Password & Session Auth** | Argon2id (`memory_cost=65536, time_cost=3, parallelism=4`) and opaque session tokens hashed via SHA-256 (`core/security.py`). | Verified; zero plaintext tokens stored. |
| **CSRF Protection** | Double-submit `pfm_csrf` HMAC-SHA256 signed cookie + `X-CSRF-Token` header verified on all non-exempt mutations (`api/deps.py`). | Verified; all Phase 2–10 routes require `get_current_user` + `verify_csrf` (only 6 public auth routes exempt). |
| **Multi-Tenant Isolation (IDOR)** | Row-level `user_id` ownership scoping across queries, uploads, OCR chunks, forecasts, conversations (`404` on foreign IDs). | Verified across all Phase 2–10 objects in `test_cross_tenant_idor_matrix_across_phases`. |
| **SQL Injection** | SQLAlchemy 2.x ORM bound queries throughout; `text()` usage audited across `backend/app/` (`SELECT 1` health probe + static Alembic `postgresql_where` expressions only). | Verified zero dynamic raw SQL string interpolation. |
| **Document & Upload Safety** | Magic-byte + PyMuPDF/Pillow structural checks (`doc_validation.py`), SHA-256 checksums, UUID storage keys, `is_relative_to` traversal prevention, `X-Content-Type-Options: nosniff`. | Verified (`test_documents_ocr.py`, `test_imports.py`). |
| **SSRF Protection** | `is_safe_public_url` (`source_validation.py`) blocks `localhost`, private/loopback/link-local/reserved IPs, `.local`/`.internal`, metadata hosts. **Gap found & fixed:** `WebhookSmsAdapter` (`sms_service.py`) lacked outbound `is_safe_public_url` validation and redirect suppression. | Hardened in `sms_service.py` (`is_safe_public_url` + `follow_redirects=False`); tested in `test_sms_webhook_ssrf_guard`. |
| **OAuth & Encrypted Credentials** | HMAC-SHA256 signed expiring `oauth_state`, redirect allowlist, Fernet encryption at rest (`token_crypto.py`). API keys strictly server-side (`config.py`). | Verified; zero secrets leaked in API responses or logs. |
| **AI & RAG Prompt Injection** | Read-only finance tools (`finance_tools.py`), untrusted control-char stripping & length bounds, `<UNTRUSTED_EVIDENCE>` isolation, PII scrubbing before public search. | Verified ledger immutability against malicious RAG content in `test_untrusted_ocr_prompt_injection_and_ledger_immutability`. |
| **HTTP Security Headers & Production Guards** | **Gap found & fixed in `main.py` & `config.py`:** `/api/docs`, `/api/redoc`, `/api/openapi.json` previously exposed in production; wildcard CORS methods/headers; missing security response headers & `TrustedHostMiddleware`. | Fixed in `main.py` + `config.py`; verified by `test_security_headers_and_request_id_correlation` & `test_production_app_hardening_and_config_guards`. |
| **Distributed Rate Limiting** | **Gap found & fixed in `rate_limit.py`:** Ignored running Valkey instance (`REDIS_URL`). | Added stdlib RESP2 TCP Valkey fixed-window counter with automatic thread-safe memory fallback; verified in `test_valkey_rate_limiter_roundtrip_and_fallback`. |

---

## 2. Detailed Security Hardening Changes Applied

1. **HTTP Security Headers & Request Correlation (`backend/app/main.py`):**
   - Added `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy: camera=(), microphone=(self), geolocation=()`, `X-XSS-Protection: 0`, `Strict-Transport-Security: max-age=31536000; includeSubDomains` (when `COOKIE_SECURE=True`), and `Cache-Control: no-store` on `/api/` responses.
   - Added `X-Request-ID` validation/generation middleware and included `request_id` in unhandled exception logs/responses without disclosing exception tracebacks.
2. **Production Exposure & Configuration Guards (`backend/app/main.py`, `backend/app/core/config.py`):**
   - Disabled `/api/openapi.json`, `/api/docs`, and `/api/redoc` when `ENVIRONMENT=production`.
   - Tightened `CORSMiddleware` from `["*"]` methods/headers to explicit allowlists (`GET`, `POST`, `PATCH`, `PUT`, `DELETE`, `OPTIONS`; `Accept`, `Authorization`, `Content-Type`, `X-CSRF-Token`, `X-Request-ID`).
   - Added optional `ALLOWED_HOSTS` configuration enforcing Starlette `TrustedHostMiddleware`.
   - Strengthened `validate_production_security()` to require non-default `SECRET_KEY` (`>= 32` chars) and reject `"*"` in `CORS_ORIGINS`.
3. **SMS Webhook SSRF Mitigation (`backend/app/services/bills/sms_service.py`):**
   - Enforced `is_safe_public_url(settings.SMS_WEBHOOK_URL)` and `follow_redirects=False` prior to webhook dispatch.
4. **Hybrid Valkey + In-Memory Rate Limiter (`backend/app/core/rate_limit.py`):**
   - Added shared Valkey rate limiting via RESP2 (`INCR` + `EXPIRE`) when `ENVIRONMENT != "test"` and `RATE_LIMIT_USE_VALKEY=true`, preserving transparent in-memory fallback on connection timeout/error.

---

## 3. Dependency & Supply-Chain Audit

- **Frontend (`npm audit --json`):** `6` dev/build-tooling advisories only (`vitest`, `vite`, `@vitest/mocker`, `esbuild`, `vite-node`, `tinypool`); `0` runtime `dependencies` vulnerabilities shipped in the production static bundle (`npm run build`). Tooling upgrades are tracked without touching locked production dependencies.
- **Backend (`requirements.txt`):** Core runtime packages up to date (`fastapi 0.165.0`, `starlette 1.10.0`, `SQLAlchemy 2.1.9`, `cryptography 50.0.2`, `argon2-cffi 25.1.0`, `urllib3 2.8.0`). Note: `pip-audit` is not installed in `backend/venv` and should be run in CI prior to external release.
