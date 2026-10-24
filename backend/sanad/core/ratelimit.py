"""Login rate limiting: failed attempts in a sliding window, per email and per client IP.

State lives in the api process's memory (the api runs a single process), so a restart clears
it. Only failures count, and a successful login clears that email's count. While a key is over
its limit every attempt is refused, even one with the right password.
"""

import time
from collections import deque
from collections.abc import Callable
from math import ceil


class LoginRateLimiter:
    def __init__(
        self,
        *,
        window_seconds: float,
        max_failures_per_email: int,
        max_failures_per_ip: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._window = window_seconds
        self._limits = {"email": max_failures_per_email, "ip": max_failures_per_ip}
        self._clock = clock
        self._failures: dict[tuple[str, str], deque[float]] = {}

    @staticmethod
    def _keys(email: str, ip: str) -> list[tuple[str, str]]:
        return [("email", email.strip().casefold()), ("ip", ip)]

    def _recent(self, key: tuple[str, str], now: float) -> deque[float]:
        stamps = self._failures.get(key, deque())
        while stamps and stamps[0] <= now - self._window:
            stamps.popleft()
        if not stamps:
            self._failures.pop(key, None)
        return stamps

    def retry_after(self, email: str, ip: str) -> int | None:
        """Seconds until an attempt is allowed again, or None if it is allowed now."""
        now = self._clock()
        waits = []
        for key in self._keys(email, ip):
            stamps = self._recent(key, now)
            excess = len(stamps) - self._limits[key[0]]
            if excess >= 0:
                # Allowed again once enough of the oldest failures have left the window.
                waits.append(stamps[excess] + self._window - now)
        return max(1, ceil(max(waits))) if waits else None

    def record_failure(self, email: str, ip: str) -> None:
        now = self._clock()
        for key in self._keys(email, ip):
            self._recent(key, now)
            self._failures.setdefault(key, deque()).append(now)

    def reset_email(self, email: str) -> None:
        self._failures.pop(self._keys(email, "")[0], None)
