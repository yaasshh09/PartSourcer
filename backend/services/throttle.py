"""In-process cooldown guard for the ?refresh=true cache bypass (spec §7/harden).

?refresh=true is a deliberate bypass that hits the free community jlcsearch
upstream directly. This bounds how often any one key may force that bypass, so
a hammering client cannot flood upstream. State is per-process (a dict keyed by
a monotonic clock) — it deliberately does not coordinate across workers; see the
README fragility note.
"""

import time
from typing import Callable


class RefreshThrottle:
    def __init__(self, cooldown_secs: float,
                 now: Callable[[], float] = time.monotonic):
        self._cooldown = cooldown_secs
        self._now = now
        self._last: dict[str, float] = {}

    def allow(self, key: str) -> bool:
        t = self._now()
        last = self._last.get(key)
        if last is not None and (t - last) < self._cooldown:
            return False
        self._last[key] = t
        return True
