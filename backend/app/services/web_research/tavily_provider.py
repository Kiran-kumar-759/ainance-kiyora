import httpx

from app.core.config import settings
from app.services.web_research.normalizer import build_normalized_source, now_iso
from app.services.web_research.schemas import (
    NormalizedWebSource,
    WebSearchRequest,
    WebSearchResponse,
)

TAVILY_SEARCH_ENDPOINT = "https://api.tavily.com/search"


class TavilyProvider:
    """Official Tavily Search API adapter (`POST https://api.tavily.com/search`)."""

    provider_id = "tavily"
    display_name = "Tavily"
    description = "AI-ready financial/news web search with relevance scoring and optional raw page text."
    supports_full_text = True

    def __init__(self, *, api_key: str | None = None, timeout: float | None = None):
        self._api_key = api_key if api_key is not None else settings.TAVILY_API_KEY
        self._timeout = timeout or settings.WEB_RESEARCH_TIMEOUT_SECONDS

    def is_configured(self) -> bool:
        return bool(self._api_key and self._api_key.strip())

    def search(self, req: WebSearchRequest) -> WebSearchResponse:
        ts = now_iso()
        if not self.is_configured():
            return WebSearchResponse(
                provider="tavily",
                query=req.query,
                status="unconfigured",
                error_message="Tavily API key is not configured on the server.",
                retrieved_at=ts,
            )

        payload = {
            "query": req.query,
            "max_results": min(req.max_results, settings.WEB_RESEARCH_MAX_RESULTS),
            "search_depth": "basic",
            "topic": req.topic,
            "include_raw_content": bool(req.include_content),
            "include_answer": False,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key.strip()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.post(TAVILY_SEARCH_ENDPOINT, json=payload, headers=headers)
        except httpx.TimeoutException:
            return WebSearchResponse(
                provider="tavily",
                query=req.query,
                status="timeout",
                error_message="Tavily search request timed out.",
                retrieved_at=ts,
            )
        except httpx.RequestError:
            return WebSearchResponse(
                provider="tavily",
                query=req.query,
                status="error",
                error_message="Unable to reach Tavily service.",
                retrieved_at=ts,
            )

        if resp.status_code in (401, 403):
            return WebSearchResponse(
                provider="tavily",
                query=req.query,
                status="error",
                error_message="Tavily rejected credentials (check TAVILY_API_KEY).",
                retrieved_at=ts,
            )
        if resp.status_code == 429:
            return WebSearchResponse(
                provider="tavily",
                query=req.query,
                status="rate_limited",
                error_message="Tavily rate limit reached. Try again later or select another provider.",
                retrieved_at=ts,
            )
        if resp.status_code >= 400:
            return WebSearchResponse(
                provider="tavily",
                query=req.query,
                status="error",
                error_message=f"Tavily returned HTTP {resp.status_code}.",
                retrieved_at=ts,
            )

        try:
            body = resp.json()
            raw_results = body.get("results") if isinstance(body, dict) else None
            if not isinstance(raw_results, list):
                raise ValueError("Invalid Tavily results payload")
        except Exception:
            return WebSearchResponse(
                provider="tavily",
                query=req.query,
                status="error",
                error_message="Tavily returned a malformed response.",
                retrieved_at=ts,
            )

        sources: list[NormalizedWebSource] = []
        for item in raw_results[: req.max_results]:
            if not isinstance(item, dict):
                continue
            norm = build_normalized_source(
                citation_id=len(sources) + 1,
                provider="tavily",
                raw_url=item.get("url"),
                title=item.get("title"),
                snippet=item.get("content"),
                content=item.get("raw_content"),
                published_at=item.get("published_date"),
                relevance_score=item.get("score"),
                retrieved_at=ts,
            )
            if norm is not None:
                sources.append(norm)

        if not sources:
            return WebSearchResponse(
                provider="tavily",
                query=req.query,
                status="empty",
                error_message="Tavily returned no safe matching public results.",
                retrieved_at=ts,
            )

        return WebSearchResponse(
            provider="tavily",
            query=req.query,
            status="completed",
            sources=sources,
            retrieved_at=ts,
        )
