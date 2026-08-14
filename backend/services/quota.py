"""Per-distributor daily call counters and exhaustion markers.

Two mechanisms, and the second one is the authority. The local counter is
an optimistic guess that keeps the hot search path free of I/O. A
distributor's own HTTP 429 is the truth: it marks that distributor
exhausted until the next 00:00 UTC, and nothing calls it again until then.

The in-process marker is the hot path. It is also written through to a
QuotaMarkerStore so a restart does not re-hammer an exhausted API.
"""

from datetime import datetime, time, timedelta, timezone
from typing import Callable, Protocol

EXHAUSTION_DETAIL = "daily limit reached, resets 00:00Z"


def _next_utc_midnight(now: datetime) -> datetime:
    """The next 00:00 UTC strictly after `now`'s date."""
    return datetime.combine(now.date() + timedelta(days=1), time.min,
                            tzinfo=timezone.utc)


class QuotaMarkerStore(Protocol):
    """Where exhaustion markers survive a restart.

    SQLite today. On Render free the file is ephemeral, so the marker does not
    survive there and the first call after a restart earns a fresh 429 that
    re-marks it, costing one wasted call per distributor per restart. On Fly,
    where the volume is durable, it works as intended. The port stays abstract
    so a Postgres adapter drops in without touching QuotaTracker.
    """

    async def get_quota_markers(self) -> dict[str, datetime]: ...

    async def put_quota_marker(self, distributor: str,
                               resets_at: datetime) -> None: ...


class QuotaTracker:
    def __init__(self, daily_limits: dict[str, int] | None = None,
                 now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
                 markers: QuotaMarkerStore | None = None,
                 loaded: dict[str, datetime] | None = None):
        self._limits = dict(daily_limits or {})
        self._now = now
        self._markers = markers
        self._counts: dict[str, int] = {}
        self._counted_on: dict[str, str] = {}
        self._exhausted_until: dict[str, datetime] = dict(loaded or {})

    def _roll(self, distributor: str) -> None:
        """Zero the counter when the UTC date has moved on."""
        today = self._now().date().isoformat()
        if self._counted_on.get(distributor) != today:
            self._counts[distributor] = 0
            self._counted_on[distributor] = today

    def record_call(self, distributor: str) -> None:
        self._roll(distributor)
        self._counts[distributor] += 1

    def calls_today(self, distributor: str) -> int:
        self._roll(distributor)
        return self._counts[distributor]

    async def mark_exhausted(self, distributor: str) -> None:
        """Called on a real 429. Upstream is the authority, so this wins over
        whatever the local counter believes.

        The write is best effort on purpose: the in-process marker is what the
        hot path reads, and a storage failure must not turn a handled quota
        error into a failed request.
        """
        until = _next_utc_midnight(self._now())
        self._exhausted_until[distributor] = until
        if self._markers is None:
            return
        try:
            await self._markers.put_quota_marker(distributor, until)
        except Exception:                       # noqa: BLE001
            pass

    def resets_at(self, distributor: str) -> datetime | None:
        self._expire(distributor)
        return self._exhausted_until.get(distributor)

    def _expire(self, distributor: str) -> None:
        until = self._exhausted_until.get(distributor)
        if until is not None and self._now() >= until:
            del self._exhausted_until[distributor]

    def is_exhausted(self, distributor: str) -> bool:
        self._expire(distributor)
        if distributor in self._exhausted_until:
            return True
        limit = self._limits.get(distributor)
        return limit is not None and self.calls_today(distributor) >= limit

    def exhaustion_detail(self, distributor: str) -> str:
        return EXHAUSTION_DETAIL
