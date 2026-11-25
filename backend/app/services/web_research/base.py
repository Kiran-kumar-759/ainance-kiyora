from typing import Protocol

from app.services.web_research.schemas import WebProviderId, WebSearchRequest, WebSearchResponse


class WebSearchProvider(Protocol):
    provider_id: WebProviderId
    display_name: str
    description: str
    supports_full_text: bool

    def is_configured(self) -> bool: ...

    def search(self, req: WebSearchRequest) -> WebSearchResponse: ...
