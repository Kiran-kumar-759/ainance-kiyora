from fastapi import HTTPException, status

from app.schemas.assistant import WebProviderId, WebProviderStatus
from app.services.web_research.base import WebSearchProvider
from app.services.web_research.firecrawl_provider import FirecrawlProvider
from app.services.web_research.langsearch_provider import LangSearchProvider
from app.services.web_research.tavily_provider import TavilyProvider

ALLOWED_PROVIDERS: tuple[WebProviderId, ...] = ("langsearch", "firecrawl", "tavily")


def get_provider(provider_id: str) -> WebSearchProvider:
    pid = (provider_id or "").strip().lower()
    if pid == "langsearch":
        return LangSearchProvider()
    if pid == "firecrawl":
        return FirecrawlProvider()
    if pid == "tavily":
        return TavilyProvider()
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Unsupported web research provider '{provider_id}'. Allowed: langsearch, firecrawl, tavily.",
    )


def list_provider_statuses() -> list[WebProviderStatus]:
    out: list[WebProviderStatus] = []
    for pid in ALLOWED_PROVIDERS:
        prov = get_provider(pid)
        out.append(
            WebProviderStatus(
                provider=prov.provider_id,
                display_name=prov.display_name,
                description=prov.description,
                configured=prov.is_configured(),
                supports_full_text=prov.supports_full_text,
            )
        )
    return out
