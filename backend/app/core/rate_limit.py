import time
from collections import defaultdict
from threading import Lock


class InMemoryRateLimiter:
    """Thread-safe sliding-window rate limiter for sensitive endpoints."""

    def __init__(self):
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def is_allowed(self, key: str, max_requests: int, window_seconds: int = 60) -> bool:
        """
        Checks if a request with given key is allowed under max_requests per window_seconds.
        Cleans up expired timestamps automatically.
        """
        now = time.time()
        cutoff = now - window_seconds

        with self._lock:
            timestamps = self._requests[key]
            # Retain only timestamps within sliding window
            valid_timestamps = [t for t in timestamps if t > cutoff]

            if len(valid_timestamps) >= max_requests:
                self._requests[key] = valid_timestamps
                return False

            valid_timestamps.append(now)
            self._requests[key] = valid_timestamps
            return True

    def clear(self):
        """Clears all tracked requests (useful in tests)."""
        with self._lock:
            self._requests.clear()


rate_limiter = InMemoryRateLimiter()
