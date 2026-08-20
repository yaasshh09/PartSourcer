"""Per-client inbound rate limiting (fixed window over a monotonic clock).

Sibling to RefreshThrottle, which bounds the deliberate ?refresh=true bypass.
This one bounds every caller instead, because a single script pointed at
/api/search fans one HTTP request out to three distributors, two of them
metered, and the free plans behind this app have no other floor.

State is per-process and deliberately so. On Vercel each warm instance keeps
its own counters, so the real ceiling is the limit times however many
instances are up, not a global cap. That is a genuine brake on one hammering
client and it is not DDoS protection; the README says exactly that rather
than implying a guarantee the architecture cannot make.

The key table is bounded. An unbounded dict keyed by client IP is itself a
memory exhaustion bug: rotate the source address and the limiter becomes the
attack. Expired windows are dropped first and the oldest survivor after that.
"""

import math
import time
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    remaining: int
    #: Whole seconds a rejected caller should wait. 0 when allowed.
    retry_after: int


class RateLimiter:
    def __init__(self, limit: int, window_secs: float, max_keys: int = 4096,
                 now: Callable[[], float] = time.monotonic):
        if limit < 1:
            raise ValueError("limit must be at least 1")
        if window_secs <= 0:
            raise ValueError("window_secs must be positive")
        if max_keys < 1:
            raise ValueError("max_keys must be at least 1")
        self._limit = limit
        self._window = window_secs
        self._max_keys = max_keys
        self._now = now
        # key -> [window_start, count_in_window]
        self._windows: dict[str, list[float]] = {}

    def check(self, key: str) -> RateLimitResult:
        """Count one request against `key` and say whether to serve it."""
        t = self._now()
        entry = self._windows.get(key)

        if entry is None or (t - entry[0]) >= self._window:
            if entry is None and len(self._windows) >= self._max_keys:
                self._evict(t)
            self._windows[key] = [t, 1]
            return RateLimitResult(True, self._limit - 1, 0)

        entry[1] += 1
        if entry[1] > self._limit:
            # Ceil so a caller told to wait 1s cannot come back at 0.4s and
            # still be inside the same window.
            retry = max(1, math.ceil(self._window - (t - entry[0])))
            return RateLimitResult(False, 0, retry)
        return RateLimitResult(True, self._limit - int(entry[1]), 0)

    def _evict(self, t: float) -> None:
        """Make room: expired windows first, then the oldest still-live one."""
        for key in [k for k, v in self._windows.items()
                    if (t - v[0]) >= self._window]:
            del self._windows[key]
        while len(self._windows) >= self._max_keys:
            oldest = min(self._windows, key=lambda k: self._windows[k][0])
            del self._windows[oldest]
