# Multi-Provider Web Research (Phase 10)

## Selectable Providers
The assistant supports three selectable live web research providers (`backend/app/services/web_research/`):
1. **`langsearch`** — `POST https://api.langsearch.com/v1/web-search` (`LANGSEARCH_API_KEY`)
   - Returns structured titles, URLs, publication dates, snippets, and optional page text.
2. **`firecrawl`** — `POST https://api.firecrawl.dev/v2/search` + selective `POST https://api.firecrawl.dev/v2/scrape` (`FIRECRAWL_API_KEY`)
   - Executes web search and selectively scrapes up to `WEB_RESEARCH_MAX_SCRAPES` SSRF-validated result URLs into Markdown when deeper page content helps.
3. **`tavily`** — `POST https://api.tavily.com/search` (`TAVILY_API_KEY`)
   - Financial/news web search with optional raw page excerpts (`include_answer: False` so final synthesis always happens under our citation-controlled orchestrator).

## No Silent Provider Fallback
Per architectural policy, `WebResearchService` executes strictly the provider chosen by the user (`web_provider` on the message, conversation default, or persisted `user_ai_preferences.default_web_provider`). If that provider is unconfigured, times out, returns HTTP 401/403, hits HTTP 429 rate limits, or fails, the exact error is surfaced honestly (`status != "completed"`) and **no other provider is substituted silently**.

## Privacy & SSRF Safeguards
- Personal numbers (`\b\d{6,}\b`) and emails are stripped from outbound public search queries (`sanitize_public_search_query`), and personal account balances or ledger amounts are never placed into web queries.
- All returned URLs are verified via `is_safe_public_url` (HTTP/HTTPS only; rejects `localhost`, `.local`, `.internal`, loopback, link-local, metadata, and private IP ranges).
- Retrieved web text is stripped of control characters, bounded (`WEB_RESEARCH_MAX_CONTENT_CHARS`), and wrapped inside `<UNTRUSTED_EVIDENCE>` data-only markers before reaching Groq.
