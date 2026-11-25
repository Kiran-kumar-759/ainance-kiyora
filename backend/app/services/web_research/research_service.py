import re

from app.services.web_research.registry import get_provider
from app.services.web_research.schemas import WebSearchRequest, WebSearchResponse

# Strip personal numbers/account/email/INR balances before crafting public web search query
_PII_PATTERN = re.compile(r"\b\d{6,}\b|\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\b")


def sanitize_public_search_query(raw_query: str) -> str:
    cleaned = _PII_PATTERN.sub("", raw_query or "").strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned[:350] or "personal finance India guidelines"


class WebResearchService:
    """
    Orchestrates public web search strictly using the caller-selected provider.
    NEVER silently switches providers when a selected provider fails or is unconfigured.
    """

    def execute_search(
        self,
        *,
        provider_id: str,
        query: str,
        max_results: int = 5,
        include_content: bool = True,
        topic: str = "finance",
    ) -> WebSearchResponse:
        provider = get_provider(provider_id)
        safe_query = sanitize_public_search_query(query)
        req = WebSearchRequest(
            query=safe_query,
            max_results=max_results,
            include_content=include_content,
            topic=topic if topic in ("general", "finance", "news") else "finance",
        )
        return provider.search(req)
