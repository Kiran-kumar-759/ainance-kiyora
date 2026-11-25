import httpx

from app.core.config import settings
from app.services.web_research.normalizer import build_normalized_source, now_iso
from app.services.web_research.schemas import (
    NormalizedWebSource,
    WebSearchRequest,
    WebSearchResponse,
)

LANGSEARCH_ENDPOINT = "https://api.langsearch.com/v1/web-search"


class LangSearchProvider:
    """Official LangSearch API v1 Web Search adapter (`POST https://api.langsearch.com/v1/web-search`)."""

    provider_id = "langsearch"
    display_name = "LangSearch"
    description = "Web search with structured snippets, freshness filters, and optional webpage text."
    supports_full_text = True

    def __init__(self, *, api_key: str | None = None, timeout: float | None = None):
        self._api_key = api_key if api_key is not None else settings.LANGSEARCH_API_KEY
        self._timeout = timeout or settings.WEB_RESEARCH_TIMEOUT_SECONDS

    def is_configured(self) -> bool:
        return bool(self._api_key and self._api_key.strip())

    def search(self, req: WebSearchRequest) -> WebSearchResponse:
        ts = now_iso()
        if not self.is_configured():
            return WebSearchResponse(
                provider="langsearch",
                query=req.query,
                status="unconfigured",
                error_message="LangSearch API key is not configured on the server.",
                retrieved_at=ts,
            )

        payload: dict = {
            "query": req.query,
            "count": min(req.max_results, settings.WEB_RESEARCH_MAX_RESULTS),
            "freshness": req.freshness or "noLimit",
        }
        if req.include_content:
            payload["contents"] = {"text": True}

        headers = {
            "Authorization": f"Bearer {self._api_key.strip()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.post(LANGSEARCH_ENDPOINT, json=payload, headers=headers)
        except httpx.TimeoutException:
            return WebSearchResponse(
                provider="langsearch",
                query=req.query,
                status="timeout",
                error_message="LangSearch search request timed out.",
                retrieved_at=ts,
            )
        except httpx.RequestError:
            return WebSearchResponse(
                provider="langsearch",
                query=req.query,
                status="error",
                error_message="Unable to reach LangSearch service.",
                retrieved_at=ts,
            )

        if resp.status_code in (401, 403):
            return WebSearchResponse(
                provider="langsearch",
                query=req.query,
                status="error",
                error_message="LangSearch rejected credentials (check LANGSEARCH_API_KEY).",
                retrieved_at=ts,
            )
        if resp.status_code == 429:
            return WebSearchResponse(
                provider="langsearch",
                query=req.query,
                status="rate_limited",
                error_message="LangSearch rate limit reached. Try again later or select another provider.",
                retrieved_at=ts,
            )
        if resp.status_code >= 400:
            return WebSearchResponse(
                provider="langsearch",
                query=req.query,
                status="error",
                error_message=f"LangSearch returned HTTP {resp.status_code}.",
                retrieved_at=ts,
            )

        try:
            body = resp.json()
            raw_items = (
                ((body.get("data") or {}).get("webPages") or {}).get("value")
                if isinstance(body, dict)
                else None
            )
            if not isinstance(raw_items, list):
                raise ValueError("Invalid webPages payload")
        except Exception:
            return WebSearchResponse(
                provider="langsearch",
                query=req.query,
                status="error",
                error_message="LangSearch returned a malformed response.",
                retrieved_at=ts,
            )

        sources: list[NormalizedWebSource] = []
        for idx, item in enumerate(raw_items[: req.max_results], start=1):
            if not isinstance(item, dict):
                continue
            norm = build_normalized_source(
                citation_id=idx,
                provider="langsearch",
                raw_url=item.get("url"),
                title=item.get("name") or item.get("title"),
                snippet=item.get("snippet") or item.get("summary"),
                content=item.get("text"),
                published_at=item.get("datePublished"),
                retrieved_at=ts,
            )
            if norm is not None:
                sources.append(norm)

        if not sources:
            return WebSearchResponse(
                provider="langsearch",
                query=req.query,
                status="empty",
                error_message="LangSearch returned no safe matching public results.",
                retrieved_at=ts,
            )

        return WebSearchResponse(
            provider="langsearch",
            query=req.query,
            status="completed",
            sources=sources,
            retrieved_at=ts,
        )
