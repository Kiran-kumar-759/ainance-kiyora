import ipaddress
import re
import socket
from urllib.parse import urlparse

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]+")
_BLOCKED_HOSTNAMES = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "metadata.google.internal"}


def is_safe_public_url(raw_url: str | None, *, resolve_dns: bool = False) -> tuple[bool, str | None, str | None]:
    """
    Validate HTTP/HTTPS source URL and reject local/private/link-local SSRF targets.
    Returns (is_safe, cleaned_url, domain).
    """
    if not raw_url or not isinstance(raw_url, str):
        return False, None, None
    cleaned = raw_url.strip()
    if len(cleaned) > 2048:
        return False, None, None

    try:
        parsed = urlparse(cleaned)
    except Exception:
        return False, None, None

    if parsed.scheme.lower() not in ("http", "https") or not parsed.hostname:
        return False, None, None

    host = parsed.hostname.lower().strip(".")
    if host in _BLOCKED_HOSTNAMES or host.endswith(".local") or host.endswith(".internal"):
        return False, None, None

    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False, None, None
    except ValueError:
        if resolve_dns:
            try:
                infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
                for info in infos:
                    ip_str = info[4][0]
                    ip_obj = ipaddress.ip_address(ip_str)
                    if (
                        ip_obj.is_private
                        or ip_obj.is_loopback
                        or ip_obj.is_link_local
                        or ip_obj.is_reserved
                        or ip_obj.is_multicast
                    ):
                        return False, None, None
            except socket.gaierror:
                return False, None, None

    return True, cleaned, host


def sanitize_untrusted_text(raw: str | None, *, max_chars: int = 3000) -> str:
    """
    Clean untrusted retrieved web/OCR text and cap length cleanly.
    Never treats retrieved content as executable instructions.
    """
    if not raw:
        return ""
    text = _CONTROL_CHARS.sub(" ", str(raw)).strip()
    text = re.sub(r"\s+", " ", text)
    if len(text) > max_chars:
        return text[:max_chars].rstrip() + "..."
    return text
