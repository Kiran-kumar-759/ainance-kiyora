# API & External Service Integration Register — Free-First Strategy

## 1. Overview & Strategy

This project follows a strict **free-first, open-source-first, and privacy-first** engineering strategy:

1. **Deterministic First:** All financial computations, balances, ledgers, EMIs, and tax calculations must use exact Python `Decimal` algorithms and deterministic business logic. Never delegate mathematical calculations to an LLM.
2. **Local Open-Source Over Cloud:** Data-sensitive operations such as document parsing and OCR must run locally on open-source libraries (e.g., PaddleOCR) without leaking user documents to paid cloud vision APIs.
3. **Generous Free Tiers for External AI:** When external cloud intelligence or external retrieval is required, prefer providers with robust, developer-friendly free tiers (Groq for ultra-fast open-weight LLM inference; Tavily for real-time web search and ground-truth citations).
4. **Provider-Independent Adapters:** Every external service or AI provider must be wrapped in an abstract interface (Adapter pattern) so that providers can be hot-swapped without changing application domain logic.
5. **Zero API Key Exposure:** External API keys must never be committed to source control, never exposed to the frontend, and never returned in API diagnostics.
6. **Data Minimization & Redaction:** Private user financial data (account numbers, names, PAN, Aadhaar, full addresses) must be sanitized and minimized before transmitting prompts to any external cloud API.

---

## 2. Service Provider Register

| Capability | Planned Provider | Engine / Details | Free-Tier Strategy & Rationale | Planned Phase |
| :--- | :--- | :--- | :--- | :--- |
| **Large Language Model (LLM)** | **Groq API** | Llama 3 / Mixtral on LPU hardware | Extremely fast inference, generous free tier limits (tokens/min, requests/min), OpenAPI-compatible endpoints. Wrapped in `LlmProvider` adapter. | **Phase 8 & 10** |
| **Web Search & Grounding** | **Tavily API** | AI-native search engine | 1,000 free searches/month API tier. Provides clean, parsed markdown and source citations for Indian financial updates/regulations. | **Phase 10** |
| **Document OCR** | **PaddleOCR** | Local open-source PP-OCRv4 | 100% free, runs locally in background worker (Celery), supports English and Indian regional scripts, zero document leakage to third parties. | **Phase 7** |
| **Database** | **PostgreSQL** | Local PostgreSQL 18 | Local relational engine, zero hosting cost during development, ACID compliant, native JSON and NUMERIC support. | **Phase 0 (Active)** |
| **Task Broker & Cache** | **Valkey / Redis** | Local Valkey 8 | High-performance open-source in-memory data store, zero hosting cost. | **Phase 0 (Active)** |
| **Financial Engine** | **Python Decimal** | Native deterministic services | Exact arithmetic, zero floating-point drift, zero cost. | **Phase 0–2** |
| **Charts & Analytics** | **Open-source libraries** | Recharts (React), NumPy/Pandas (Python) | Completely client-side and open-source backend analytical processing. | **Phase 5 & 6** |

---

## 3. Provider Details & Architecture

### 3.1 LLM: Groq API
- **Role:** High-velocity reasoning, intent classification, natural language query translation to structured filters, conversational financial assistant.
- **Service Boundary:**
  - `app/services/ai/base.py`: Abstract `LlmServiceAdapter` defining `generate()`, `chat()`, and `structured_output()`.
  - `app/services/ai/groq_adapter.py`: Implementation utilizing Groq client or OpenAI-compatible client.
- **Privacy Rule:** Prompts must redact PII (Personally Identifiable Information) and exact bank account identifiers. Only generalized transaction categories, relative amounts, or user prompt queries may be transmitted.
- **Quota & Fallback Strategy:**
  - When rate limits (429) or token quotas are reached, the system must gracefully fall back to local rule-based responses and inform the user of quota refresh windows.

### 3.2 Web Search: Tavily API
- **Role:** External retrieval for financial news, RBI policy announcements, inflation data, and current tax slab information.
- **Service Boundary:**
  - `app/services/search/base.py`: Abstract `SearchServiceAdapter` defining `search(query, max_results)`.
  - `app/services/search/tavily_adapter.py`: Implementation using Tavily search endpoint.
- **Quota & Fallback Strategy:**
  - Strict caching layer (Valkey/Redis with 24-hour TTL) for common financial search topics to conserve the 1,000 queries/month free tier.
  - Returns clear source URLs and timestamps in tool outputs.

### 3.3 Document OCR: Local PaddleOCR
- **Role:** Processing Indian utility bills, credit card statements, fuel receipts, and invoice documents.
- **Engine:** Local open-source PaddleOCR running inside background tasks (Celery worker).
- **Hard Rule:** **No paid cloud vision APIs** (such as Google Cloud Vision, AWS Textract, or Azure Document Intelligence).
- **Pipeline (Phase 7):**
  1. Image preprocessing (deskew, contrast enhancement, grayscale normalization).
  2. Text detection and recognition via local model weights.
  3. Structured regex and rule-based extraction for Indian GST numbers, total amounts, dates, and vendor names.
  4. Confidence score calculation with human-in-the-loop review UI for low-confidence fields (< 85%).

---

## 4. Environment Variable Conventions

During Phase 0, external API keys are **not required or validated**. For future phases, the following naming conventions are established:

```bash
# External AI & Search Providers (Future Phases 7, 8, 10)
# DO NOT CONFIGURE OR REQUIRE IN PHASE 0

# Groq LLM API Key (Phase 8 & 10)
GROQ_API_KEY=

# Groq Model Selection (default: llama-3.3-70b-versatile or llama-3.1-8b-instant)
GROQ_MODEL=llama-3.3-70b-versatile

# Tavily Web Search API Key (Phase 10)
TAVILY_API_KEY=

# Local OCR Settings (Phase 7)
OCR_ENGINE=paddleocr
OCR_ENABLE_GPU=false
OCR_CONFIDENCE_THRESHOLD=0.85
```

---

## 5. Staged Implementation Roadmap

```mermaid
flowchart LR
    P0["Phase 0<br/>Foundation & Contracts"] --> P7["Phase 7<br/>Local PaddleOCR<br/>(Bills & Receipts)"]
    P7 --> P8["Phase 8<br/>Groq LLM<br/>(Value-Add Intelligence)"]
    P8 --> P10["Phase 10<br/>Groq + Tavily<br/>(Tool Calling & Search)"]
```

### Phase 7: Local Bill & Receipt OCR
- Implement `OcrService` using local PaddleOCR.
- Benchmark with representative Indian receipts (thermal fuel receipts, restaurant GST bills, Amazon India invoices, utility electricity bills).
- Zero cloud API dependency.

### Phase 8: Value-Add LLM Assistance
- Integrate Groq API via adapter.
- Restrict LLM usage strictly to tasks where deterministic rules and local ML are insufficient (e.g., messy transaction narrative parsing, unstructured merchant name cleanup).
- Deterministic rules always execute first.

### Phase 10: AI Financial Assistant with Tavily Search
- Controlled function calling / tool calling via Groq.
- Tavily search queries for current Indian tax updates, interest rates, and financial news.
- Enforce strict privacy redaction, response citations, query caching, and graceful quota depletion handlers.
