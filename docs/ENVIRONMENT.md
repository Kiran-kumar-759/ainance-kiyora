# Environment Variables & Configuration (Phase 7 Update)

## Document Storage & Local OCR
- `DOCUMENT_STORAGE_DIR=uploads/documents` — Private local filesystem root for uploaded documents (never served publicly).
- `DOCUMENT_MAX_FILE_SIZE_BYTES=15728640` — Upload limit (15 MB default).
- `DOCUMENT_MAX_PDF_PAGES=20` — Bounded maximum PDF pages processed per job.
- `OCR_ENGINE=rapidocr` — Provider choice (`rapidocr` local CPU PP-OCR ONNX models [default for Python 3.14 compatibility] or `paddleocr`).
- `OCR_USE_ANGLE_CLS=true` — Orientation classification enabled.
- `OCR_WORKER_ENABLED=true` — Enables background OCR worker inside FastAPI lifespan.
- `OCR_WORKER_INTERVAL_SECONDS=15` — Worker poll interval.
- `OCR_WORKER_MAX_CONCURRENT=2` — Bounded concurrent OCR worker threads.
- `OCR_JOB_MAX_ATTEMPTS=3` — Maximum bounded retry attempts on OCR failure.
- `DOCUMENT_UPLOAD_RATE_LIMIT_MAX=30` — Per-user uploads/processing requests per minute.

## Gmail OAuth 2.0 & Email Ingestion
- `GOOGLE_OAUTH_CLIENT_ID` — Google Cloud OAuth 2.0 Web Client ID (blank by default; required for live Gmail sync).
- `GOOGLE_OAUTH_CLIENT_SECRET` — Google Cloud OAuth 2.0 Client Secret (never commit real secrets).
- `GOOGLE_OAUTH_REDIRECT_URI=http://127.0.0.1:8000/api/v1/email/gmail/callback`
- `GMAIL_SCOPES=["https://www.googleapis.com/auth/gmail.readonly"]` — Strictly read-only mailbox scope.
- `EMAIL_TOKEN_ENCRYPTION_KEY` — Optional explicit 32-byte URL-safe base64 Fernet key (falls back to key derived from `SECRET_KEY` in dev/test).
- `EMAIL_SYNC_DEFAULT_QUERY` — Controlled search filter for bills, invoices, receipts & statements.
- `EMAIL_SYNC_MAX_MESSAGES=25` — Bounded maximum messages scanned per sync run.

## Incoming SMS Ingestion Boundary
- `SMS_INGESTION_ENABLED=false`
- `SMS_INGESTION_PROVIDER=none`
- Phase 5 outgoing reminder variables (`SMTP_ENABLED`, `SMS_ENABLED`, `SMS_PROVIDER`, `SMS_WEBHOOK_URL`) remain unchanged.


## Phase 8 — AI Expense Intelligence & Optional Groq Adapter
- `AI_WORKER_ENABLED=true` — Enables PostgreSQL-backed `AiIntelligenceWorker` inside FastAPI lifespan (automatically disabled when `ENVIRONMENT=test`).
- `AI_WORKER_INTERVAL_SECONDS=20` — Poll interval for claiming queued `ai_processing_jobs`.
- `GROQ_ENABLED=false` — Explicit toggle for optional Groq LLM fallback & insight phrasing. System operates 100% deterministically locally when `false`.
- `GROQ_API_KEY` — Optional Groq API key read exclusively on the backend (never committed or exposed to frontend).
- `GROQ_MODEL=llama-3.3-70b-versatile` — Target Groq model when `GROQ_ENABLED=true`.
- `GROQ_TIMEOUT_SECONDS=12.0` — Bounded request timeout per Groq completion call.
- `GROQ_MAX_RETRIES=2` — Bounded client retry limit on transient Groq network failures.


## Phase 9 — Financial Forecasting
- Phase 9 forecasting uses deterministic statistical engines on PostgreSQL data and `AiIntelligenceWorker` (`AI_WORKER_ENABLED`, `AI_WORKER_INTERVAL_SECONDS`) with zero additional mandatory environment secrets or external APIs.


## Phase 10 — AI Assistant, Web Research Providers & RAG
- `LANGSEARCH_API_KEY` — Optional server-side credential for LangSearch Web Search (`https://api.langsearch.com/v1/web-search`). Never exposed to frontend or committed to Git.
- `FIRECRAWL_API_KEY` — Optional server-side credential for Firecrawl Search & Scrape v2 (`https://api.firecrawl.dev/v2/search`, `/v2/scrape`).
- `TAVILY_API_KEY` — Optional server-side credential for Tavily Search (`https://api.tavily.com/search`).
- `DEFAULT_WEB_RESEARCH_PROVIDER=tavily` — Default initial web research provider (`langsearch` | `firecrawl` | `tavily`).
- `WEB_RESEARCH_TIMEOUT_SECONDS=12.0` — Bounded timeout per outbound search/scrape call.
- `WEB_RESEARCH_MAX_RESULTS=5` — Bounded result count fetched per web search turn.
- `WEB_RESEARCH_MAX_SCRAPES=2` — Maximum SSRF-validated URLs scraped via Firecrawl per search turn.
- `WEB_RESEARCH_MAX_CONTENT_CHARS=4000` — Per-source excerpt character cap.
- `ASSISTANT_MAX_CONTEXT_MESSAGES=12` — Bounded conversation turn history window passed to LLM synthesis.
- Reuses `GROQ_ENABLED`, `GROQ_API_KEY`, and `GROQ_MODEL` (all disabled/blank in automated tests).


## Phase 11 — Production Hardening, Host Allowlisting & Shared Rate Limiting
- `ALLOWED_HOSTS=[]` — Optional comma-separated or JSON array of permitted `Host` headers enforced via `TrustedHostMiddleware`.
- `RATE_LIMIT_USE_VALKEY=true` — Enables shared Valkey (`REDIS_URL`) rate limiting outside `ENVIRONMENT=test`, with automatic thread-safe in-memory fallback when Valkey is unreachable.
- `ENVIRONMENT=production` enforces `COOKIE_SECURE=true`, rejects wildcard `*` in `CORS_ORIGINS`, enforces `len(SECRET_KEY) >= 32`, and disables `/api/docs`, `/api/redoc`, and `/api/openapi.json`.
