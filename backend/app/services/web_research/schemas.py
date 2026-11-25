from typing import Literal

from pydantic import BaseModel, Field

WebProviderId = Literal["langsearch", "firecrawl", "tavily"]


class WebSearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=400)
    max_results: int = Field(default=5, ge=1, le=8)
    include_content: bool = True
    topic: Literal["general", "finance", "news"] = "finance"
    freshness: str = "noLimit"


class NormalizedWebSource(BaseModel):
    citation_id: int
    provider: WebProviderId
    title: str
    url: str
    domain: str
    snippet: str
    content: str | None = None
    published_at: str | None = None
    retrieved_at: str
    source_type: str = "external_web"
    favicon_url: str | None = None
    relevance_score: float | None = None
    content_available: bool = False
    fetch_status: str = "snippet_only"  # full_content, snippet_only, scrape_failed_snippet_only


class WebSearchResponse(BaseModel):
    provider: WebProviderId
    query: str
    status: Literal["completed", "unconfigured", "empty", "rate_limited", "timeout", "error"]
    sources: list[NormalizedWebSource] = Field(default_factory=list)
    error_message: str | None = None
    retrieved_at: str
