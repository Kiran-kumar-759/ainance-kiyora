import datetime as dt

from app.core.config import settings
from app.services.web_research.schemas import NormalizedWebSource, WebProviderId
from app.services.web_research.source_validation import is_safe_public_url, sanitize_untrusted_text


def now_iso() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


def build_normalized_source(
    *,
    citation_id: int,
    provider: WebProviderId,
    raw_url: str | None,
    title: str | None,
    snippet: str | None,
    content: str | None = None,
    published_at: str | None = None,
    relevance_score: float | None = None,
    fetch_status: str | None = None,
    retrieved_at: str | None = None,
) -> NormalizedWebSource | None:
    safe, clean_url, domain = is_safe_public_url(raw_url)
    if not safe or not clean_url or not domain:
        return None

    clean_title = sanitize_untrusted_text(title or domain, max_chars=220) or domain
    clean_snippet = sanitize_untrusted_text(snippet or "", max_chars=650)
    clean_content = (
        sanitize_untrusted_text(content, max_chars=settings.WEB_RESEARCH_MAX_CONTENT_CHARS)
        if content
        else None
    )
    has_content = bool(clean_content and len(clean_content) > len(clean_snippet))
    status = fetch_status or ("full_content" if has_content else "snippet_only")

    return NormalizedWebSource(
        citation_id=citation_id,
        provider=provider,
        title=clean_title,
        url=clean_url,
        domain=domain,
        snippet=clean_snippet or (clean_content[:400] if clean_content else "Source retrieved cleanly."),
        content=clean_content,
        published_at=published_at,
        retrieved_at=retrieved_at or now_iso(),
        source_type="external_web",
        favicon_url=f"https://www.google.com/s2/favicons?domain={domain}&sz=32",
        relevance_score=round(float(relevance_score), 4) if relevance_score is not None else None,
        content_available=bool(clean_content),
        fetch_status=status,
    )
