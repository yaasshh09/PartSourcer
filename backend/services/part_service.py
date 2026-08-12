"""Registry, fan-out, merge, and status. The layer routes will see.

An adapter knows one distributor. This knows that there are three of them,
that any of them can be missing or broken, and that saying so plainly is
better than a 502 when two of them answered.
"""

import asyncio
from typing import Awaitable, Callable

from models.offer import DistributorStatus
from services.adapters.base import DistributorAdapter, RawListing, UpstreamError
from services.quota import QuotaTracker

ALL_DISTRIBUTORS: tuple[str, ...] = ("lcsc", "mouser", "digikey")

NO_CREDENTIALS = "no credentials configured"


def disabled_reasons(settings) -> dict[str, str]:
    """Which distributors are off, and why. Absent means enabled.

    Enablement is derived from secrets rather than declared in config, so
    the deployed app behaves exactly as it does today until a key exists,
    and DigiKey stays dark with no code branch.
    """
    off: dict[str, str] = {}
    if not (settings.mouser_api_key or "").strip():
        off["mouser"] = NO_CREDENTIALS
    if not ((settings.digikey_client_id or "").strip()
            and (settings.digikey_client_secret or "").strip()):
        off["digikey"] = NO_CREDENTIALS
    return off


Call = Callable[[DistributorAdapter], Awaitable[list[RawListing]]]


class PartService:
    """Fan out to every enabled distributor, then report what happened.

    A partial failure is a partial answer, never an error. The caller gets
    whatever answered plus a status per distributor, and decides from there.
    """

    def __init__(self, adapters: dict[str, DistributorAdapter],
                 quota: QuotaTracker,
                 disabled: dict[str, str] | None = None,
                 timeout_secs: float = 8.0):
        self._adapters = adapters
        self._quota = quota
        self._disabled = dict(disabled or {})
        self._timeout = timeout_secs

    def _status(self, distributor: str, state: str, detail: str | None = None,
                as_of=None) -> DistributorStatus:
        return DistributorStatus(distributor=distributor, state=state,
                                 detail=detail, as_of=as_of)

    async def _call_one(self, name: str, make: Call):
        """Never raises. Every failure becomes a status."""
        adapter = self._adapters[name]
        try:
            listings = await asyncio.wait_for(make(adapter), self._timeout)
        except (asyncio.TimeoutError, TimeoutError):
            return [], self._status(name, "timeout",
                                    f"{name} exceeded {self._timeout:g}s")
        except UpstreamError as exc:
            if exc.kind == "quota":
                # Upstream is the authority on its own quota.
                self._quota.mark_exhausted(name)
                return [], self._status(name, "quota_exhausted",
                                        self._quota.exhaustion_detail(name))
            state = "timeout" if exc.kind == "timeout" else "unavailable"
            return [], self._status(name, state, str(exc))
        except Exception as exc:                    # noqa: BLE001
            return [], self._status(name, "unavailable", f"{name} failed: {exc}")

        self._quota.record_call(name)
        as_of = min((r.as_of for r in listings), default=None)
        return listings, self._status(name, "ok", None, as_of)

    async def fan_out(self, make: Call
                      ) -> tuple[list[RawListing], list[DistributorStatus]]:
        statuses: list[DistributorStatus] = []
        pending: list[tuple[str, asyncio.Task]] = []

        for name in ALL_DISTRIBUTORS:
            if name in self._disabled:
                statuses.append(self._status(name, "disabled",
                                             self._disabled[name]))
                continue
            if name not in self._adapters:
                continue
            if self._quota.is_exhausted(name):
                # Skipped without a call, which is the whole point of the marker.
                statuses.append(self._status(name, "quota_exhausted",
                                             self._quota.exhaustion_detail(name)))
                continue
            pending.append((name, asyncio.ensure_future(self._call_one(name, make))))

        listings: list[RawListing] = []
        outcomes = await asyncio.gather(*(t for _, t in pending),
                                        return_exceptions=True)
        for (name, _), outcome in zip(pending, outcomes):
            if isinstance(outcome, BaseException):
                statuses.append(self._status(name, "unavailable",
                                             f"{name} failed: {outcome}"))
                continue
            got, status = outcome
            listings.extend(got)
            statuses.append(status)

        statuses.sort(key=lambda s: ALL_DISTRIBUTORS.index(s.distributor))
        return listings, statuses
