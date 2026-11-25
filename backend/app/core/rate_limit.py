import logging
import socket
import threading
import time
from collections import defaultdict
from urllib.parse import urlparse

from app.core.config import settings

logger = logging.getLogger(__name__)


def _encode_resp_array(parts: list[str]) -> bytes:
    out = [f"*{len(parts)}\r\n".encode("ascii")]
    for part in parts:
        raw = str(part).encode("utf-8")
        out.append(f"${len(raw)}\r\n".encode("ascii") + raw + b"\r\n")
    return b"".join(out)


def _read_resp_line(sock: socket.socket) -> bytes:
    buf = bytearray()
    while not buf.endswith(b"\r\n"):
        chunk = sock.recv(1)
        if not chunk:
            raise ConnectionError("Unexpected EOF reading Valkey RESP response.")
        buf.extend(chunk)
        if len(buf) > 4096:
            raise ValueError("Valkey RESP response line too long.")
    return bytes(buf[:-2])


def _valkey_incr_window(redis_url: str, key: str, window_seconds: int, timeout: float = 0.5) -> int:
    """
    Lightweight RESP2 fixed-window counter on Valkey/Redis over TCP without extra packages.
    Raises on connection or protocol error so callers can cleanly fall back to in-memory limiting.
    """
    parsed = urlparse(redis_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 6379
    db_index = 0
    if parsed.path and parsed.path.strip("/").isdigit():
        db_index = int(parsed.path.strip("/"))

    bucket = int(time.time() // max(1, window_seconds))
    namespaced_key = f"pfm:rl:{key}:{bucket}"

    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        if parsed.password:
            auth_parts = ["AUTH", parsed.username, parsed.password] if parsed.username else ["AUTH", parsed.password]
            sock.sendall(_encode_resp_array(auth_parts))
            line = _read_resp_line(sock)
            if line.startswith(b"-"):
                raise PermissionError(line.decode("utf-8", errors="ignore"))
        if db_index > 0:
            sock.sendall(_encode_resp_array(["SELECT", str(db_index)]))
            line = _read_resp_line(sock)
            if line.startswith(b"-"):
                raise RuntimeError(line.decode("utf-8", errors="ignore"))

        sock.sendall(_encode_resp_array(["INCR", namespaced_key]))
        incr_line = _read_resp_line(sock)
        if not incr_line.startswith(b":"):
            raise ValueError(f"Unexpected Valkey INCR reply: {incr_line!r}")
        count = int(incr_line[1:])

        if count == 1:
            sock.sendall(_encode_resp_array(["EXPIRE", namespaced_key, str(max(2, window_seconds + 1))]))
            _read_resp_line(sock)

        return count


class InMemoryRateLimiter:
    """
    Hybrid rate limiter with thread-safe in-memory sliding window and optional
    Valkey shared backing for multi-worker deployments.
    Preserves `_requests` attribute for deterministic unit test isolation.
    """

    def __init__(self):
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def _use_valkey(self) -> bool:
        return (
            settings.ENVIRONMENT.lower() != "test"
            and bool(getattr(settings, "RATE_LIMIT_USE_VALKEY", False))
            and bool(getattr(settings, "REDIS_URL", ""))
        )

    def _is_allowed_memory(self, key: str, max_requests: int, window_seconds: int) -> bool:
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            timestamps = [ts for ts in self._requests[key] if ts > cutoff]
            if len(timestamps) >= max_requests:
                self._requests[key] = timestamps
                return False
            timestamps.append(now)
            self._requests[key] = timestamps
            return True

    def is_allowed(self, key: str, max_requests: int = 10, window_seconds: int = 60) -> bool:
        """Checks whether a request key is permitted under the rate limit window."""
        if self._use_valkey():
            try:
                count = _valkey_incr_window(settings.REDIS_URL, key, window_seconds)
                return count <= max_requests
            except Exception as exc:
                logger.warning("Valkey rate-limit unavailable (%s); falling back to memory.", exc)
        return self._is_allowed_memory(key, max_requests, window_seconds)

    def clear(self, key: str | None = None):
        with self._lock:
            if key:
                self._requests.pop(key, None)
            else:
                self._requests.clear()


rate_limiter = InMemoryRateLimiter()
