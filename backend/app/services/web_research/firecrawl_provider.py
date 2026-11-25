import httpx

from app.core.config import settings
from app.services.web_research.normalizer import build_normalized_source, now_iso
from app.services.web_research.schemas import (
    NormalizedWebSource,
    WebSearchRequest,
    WebSearchResponse,
)
from app.services.web_research.source_validation import is_safe_public_url

FIRECRAWL_SEARCH_ENDPOINT = "https://api.firecrawl.dev/v2/search"
FIRECRAWL_SCRAPE_ENDPOINT = "https://api.firecrawl.dev/v2/scrape"


class FirecrawlProvider:
    """
    Official Firecrawl v2 Search + Selective Scrape adapter.
    Executes controlled web search first, then selectively scrapes up to WEB_RESEARCH_MAX_SCRAPES
    SSRF-validated result URLs as clean Markdown when full content isn't already attached.
    """

    provider_id = "firecrawl"
    display_name = "Firecrawl"
    description = "Web search + selective clean Markdown scraping for deeper policy/article extraction."
    supports_full_text = True

    def __init__(self, *, api_key: str | None = None, timeout: float | None = None):
        self._api_key = api_key if api_key is not None else settings.FIRECRAWL_API_KEY
        self._timeout = timeout or settings.WEB_RESEARCH_TIMEOUT_SECONDS

    def is_configured(self) -> bool:
        return bool(self._api_key and self._api_key.strip())

    def search(self, req: WebSearchRequest) -> WebSearchResponse:
        ts = now_iso()
        if not self.is_configured():
            return WebSearchResponse(
                provider="firecrawl",
                query=req.query,
                status="unconfigured",
                error_message="Firecrawl API key is not configured on the server.",
                retrieved_at=ts,
            )

        headers = {
            "Authorization": f"Bearer {self._api_key.strip()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload = {
            "query": req.query,
            "limit": min(req.max_results, settings.WEB_RESEARCH_MAX_RESULTS),
            "sources": [{"type": "web"}],
            "country": "IN",
            "highlights": True,
        }

        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.post(FIRECRAWL_SEARCH_ENDPOINT, json=payload, headers=headers)
        except httpx.TimeoutException:
            return WebSearchResponse(
                provider="firecrawl",
                query=req.query,
                status="timeout",
                error_message="Firecrawl search request timed out.",
                retrieved_at=ts,
            )
        except httpx.RequestError:
            return WebSearchResponse(
                provider="firecrawl",
                query=req.query,
                status="error",
                error_message="Unable to reach Firecrawl service.",
                retrieved_at=ts,
            )

        if resp.status_code in (401, 403):
            return WebSearchResponse(
                provider="firecrawl",
                query=req.query,
                status="error",
                error_message="Firecrawl rejected credentials (check FIRECRAWL_API_KEY).",
                retrieved_at=ts,
            )
        if resp.status_code == 429:
            return WebSearchResponse(
                provider="firecrawl",
                query=req.query,
                status="rate_limited",
                error_message="Firecrawl rate limit reached. Try again later or select another provider.",
                retrieved_at=ts,
            )
        if resp.status_code >= 400:
            return WebSearchResponse(
                provider="firecrawl",
                query=req.query,
                status="error",
                error_message=f"Firecrawl returned HTTP {resp.status_code}.",
                retrieved_at=ts,
            )

        try:
            body = resp.json()
            raw_data = body.get("data") if isinstance(body, dict) else None
            if isinstance(raw_data, dict):
                raw_items = raw_data.get("web") or raw_data.get("results") or []
            elif isinstance(raw_data, list):
                raw_items = raw_data
            else:
                raise ValueError("Invalid Firecrawl data structure")
            if not isinstance(raw_items, list):
                raise ValueError("Invalid Firecrawl results")
        except Exception:
            return WebSearchResponse(
                provider="firecrawl",
                query=req.query,
                status="error",
                error_message="Firecrawl returned a malformed search response.",
                retrieved_at=ts,
            )

        sources: list[NormalizedWebSource] = []
        scrapes_done = 0
        for item in raw_items[: req.max_results]:
            if not isinstance(item, dict):
                continue
            url = item.get("url")
            markdown_text = item.get("markdown")
            highlights = item.get("highlights")
            snippet = item.get("description") or (
                " ".join(highlights) if isinstance(highlights, list) else None
            )
            fetch_status = "full_content" if markdown_text else "snippet_only"

            # Selective scrape ONLY on top SSRF-safe URLs when content is requested & absent
            if (
                req.include_content
                and not markdown_text
                and scrapes_done < settings.WEB_RESEARCH_MAX_SCRAPES
                and url
            ):
                safe, clean_url, _ = is_safe_public_url(url)
                if safe and clean_url:
                    scrapes_done += 1
                    try:
                        with httpx.Client(timeout=self._timeout) as client:
                            s_resp = client.post(
                                FIRECRAWL_SCRAPE_ENDPOINT,
                                json={
                                    "url": clean_url,
                                    "formats": ["markdown"],
                                    "onlyMainContent": True,
                                },
                                headers=headers,
                            )
                        if s_resp.status_code == 200:
                            s_data = s_resp.json().get("data") or {}
                            if isinstance(s_data, dict) and s_data.get("markdown"):
                                markdown_text = s_data["markdown"]
                                fetch_status = "full_content"
                            else:
                                fetch_status = "scrape_failed_snippet_only"
                        else:
                            fetch_status = "scrape_failed_snippet_only"
                    except Exception:
                        fetch_status = "scrape_failed_snippet_only"

            norm = build_normalized_source(
                citation_id=len(sources) + 1,
                provider="firecrawl",
                raw_url=url,
                title=item.get("title") or (item.get("metadata") or {}).get("title"),
                snippet=snippet,
                content=markdown_text,
                fetch_status=fetch_status,
                retrieved_at=ts,
            )
            if norm is not None:
                sources.append(norm)

        if not sources:
            return WebSearchResponse(
                provider="firecrawl",
                query=req.query,
                status="empty",
                error_message="Firecrawl returned no safe matching public results.",
                retrieved_at=ts,
            )

        return WebSearchResponse(
            provider="firecrawl",
            query=req.query,
            status="completed",
            sources=sources,
            retrieved_at=ts,
        )
