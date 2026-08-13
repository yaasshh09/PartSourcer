"""Registry, fan-out, merge, and status. The layer routes will see.

An adapter knows one distributor. This knows that there are three of them,
that any of them can be missing or broken, and that saying so plainly is
better than a 502 when two of them answered.
"""

import asyncio
from datetime import datetime
from typing import Awaitable, Callable

from models.offer import DistributorStatus, Offer, Part, SearchResponseV2
from services.adapters.base import DistributorAdapter, RawListing, UpstreamError
from services.cheapest import compute_cheapest
from services.matching import (normalize_exact, packaging_note,
                               strip_packaging_suffix)
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


def _first_populated(rows: list[RawListing], attr: str) -> str | None:
    """First non-empty value across a part's listings.

    Rows arrive in spec precedence order (see _ranked_listings), so this
    closes v1's honest gaps: LCSC carries package but no brand or
    datasheet, and Mouser and DigiKey carry brand and datasheet but no
    package.
    """
    for row in rows:
        value = getattr(row, attr)
        if value:
            return value
    return None


def _ranked_listings(rows: list[tuple[RawListing, str, str | None]]
                     ) -> list[RawListing]:
    """A part's listings in spec precedence order.

    Exact-tier first, so a folded packaging variant never gets to name the
    part or describe it, then canonical distributor order, so the answer
    does not depend on which distributor happened to be seen first. The
    grouping in merge orders rows by first-seen key, which is neither.
    """
    def rank(item: tuple[RawListing, str, str | None]) -> tuple[int, int]:
        row, tier, _ = item
        return (0 if tier == "exact" else 1,
                ALL_DISTRIBUTORS.index(row.distributor))

    return [row for row, _, _ in sorted(rows, key=rank)]


def _fold_target(key: str, present: dict[str, list[RawListing]]) -> str:
    """The part key a listing key folds into, followed to its end.

    A variant folds only into a base that is itself a real result, because
    inventing a base we never saw would be a claim we cannot support. The
    walk repeats rather than stopping after one strip: with X, X-TR and
    X-TR-REEL all in the results, X-TR-REEL belongs on X, not on an X-TR
    that has itself been folded away and so claims no listing of its own.
    Every step strictly shortens the key, so this terminates.
    """
    target = key
    while True:
        base, suffix = strip_packaging_suffix(target)
        if not suffix or base not in present:
            return target
        target = base


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
                as_of: datetime | None = None) -> DistributorStatus:
        return DistributorStatus(distributor=distributor, state=state,
                                 detail=detail, as_of=as_of)

    async def _call_one(self, name: str, make: Call
                        ) -> tuple[list[RawListing], DistributorStatus]:
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
            # Type only, never the message. A detail we did not compose can
            # carry anything the exception saw, and httpx puts the request
            # URL in its message while the Mouser key rides in the query
            # string. An unmapped failure gives a caller nothing to act on
            # anyway, so there is nothing to lose by dropping it.
            return [], self._status(name, "unavailable",
                                    f"{name} failed: {type(exc).__name__}")

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
                if not isinstance(outcome, Exception):
                    # CancelledError and friends are not this distributor's
                    # failure to report, they are the caller's to see.
                    raise outcome
                statuses.append(self._status(name, "unavailable",
                                             f"{name} failed: {outcome}"))
                continue
            got, status = outcome
            listings.extend(got)
            statuses.append(status)

        # gather() preserves input order, but disabled and quota_exhausted
        # statuses are appended during the loop above while the pending
        # ones are appended after gather, so insertion order interleaves
        # wrong. Sort back into canonical order to fix that.
        statuses.sort(key=lambda s: ALL_DISTRIBUTORS.index(s.distributor))
        return listings, statuses

    def merge(self, listings: list[RawListing],
              sources: list[DistributorStatus]) -> list[Part]:
        """Group listings into parts by canonical MPN, two tiers deep."""
        exact: dict[str, list[RawListing]] = {}
        seen: list[str] = []
        for row in listings:
            key = normalize_exact(row.mpn)
            if not key:
                continue                      # not a part, drop it
            if key not in exact:
                exact[key] = []
                seen.append(key)
            exact[key].append(row)

        # Fold each variant onto the base it really belongs to. A variant
        # with no base among the results stands alone as its own part.
        grouped: dict[str, list[tuple[RawListing, str, str | None]]] = {}
        order: list[str] = []
        for key in seen:
            target = _fold_target(key, exact)
            if target == key:
                tier, note = "exact", None
            else:
                # Name the whole difference between what was listed and
                # what the part is called, not just the last suffix
                # stripped, so a reader can check the claim by eye.
                tier, note = "packaging", packaging_note(key[len(target):])
            if target not in grouped:
                grouped[target] = []
                order.append(target)
            grouped[target].extend((row, tier, note) for row in exact[key])

        parts: list[Part] = []
        for key in order:
            rows = grouped[key]
            offers = [
                Offer(distributor=row.distributor, sku=row.sku,
                      mpn_as_listed=row.mpn, match_tier=tier, match_note=note,
                      stock=row.stock, in_stock=row.in_stock,
                      price_usd=row.price, price_breaks=row.price_breaks,
                      currency=row.currency, product_url=row.product_url,
                      as_of=row.as_of)
                for row, tier, note in rows
            ]
            claim, reason = compute_cheapest(offers, sources)
            specs = _ranked_listings(rows)
            parts.append(Part(
                mpn_key=key,
                mpn=specs[0].mpn,
                brand=_first_populated(specs, "brand"),
                package=_first_populated(specs, "package") or "",
                description=_first_populated(specs, "description") or "",
                datasheet_url=_first_populated(specs, "datasheet_url"),
                offers=offers,
                cheapest=claim,
                cheapest_unavailable_reason=reason,
            ))
        return parts

    async def search(self, query: str, limit: int,
                     page: int = 1) -> SearchResponseV2:
        # An adapter takes a limit and no offset, so paging happens here:
        # ask upstream for enough rows to reach the page, then window the
        # merged parts locally. v1 pages the same way in datasource.search.
        # Echoing a page number over page-1 results would be a lie.
        want = page * limit
        listings, sources = await self.fan_out(
            lambda adapter: adapter.search(query, want))
        parts = self.merge(listings, sources)
        start = (page - 1) * limit
        return SearchResponseV2(page=page, query=query,
                                results=parts[start:start + limit],
                                sources=sources)

    @property
    def timeout_secs(self) -> float:
        return self._timeout

    def adapter_names(self) -> list[str]:
        return [n for n in ALL_DISTRIBUTORS if n in self._adapters]

    def disabled_names(self) -> list[str]:
        return [n for n in ALL_DISTRIBUTORS if n in self._disabled]


def build_part_service(settings, lcsc_client: "httpx.AsyncClient"):
    """Build the registry from whichever credentials exist.

    Returns (service, created_clients). The caller owns the returned
    clients and must close them on shutdown. The LCSC client is passed in
    because it already exists and is shared with the v1 datasource.
    """
    import httpx

    from services.adapters.digikey import DigiKeyAdapter
    from services.adapters.digikey_auth import DigiKeyTokenClient
    from services.adapters.lcsc import LcscAdapter
    from services.adapters.mouser import MouserAdapter

    off = disabled_reasons(settings)
    adapters: dict[str, DistributorAdapter] = {"lcsc": LcscAdapter(lcsc_client)}
    created: list[httpx.AsyncClient] = []

    if "mouser" not in off:
        client = httpx.AsyncClient(base_url=settings.mouser_base_url,
                                   timeout=settings.distributor_timeout_secs)
        created.append(client)
        adapters["mouser"] = MouserAdapter(client, settings.mouser_api_key)

    if "digikey" not in off:
        client = httpx.AsyncClient(base_url=settings.digikey_base_url,
                                   timeout=settings.distributor_timeout_secs)
        created.append(client)
        tokens = DigiKeyTokenClient(client, settings.digikey_client_id,
                                    settings.digikey_client_secret)
        adapters["digikey"] = DigiKeyAdapter(client, tokens,
                                             settings.digikey_client_id)

    # No daily_limits on purpose, so the local counter is unlimited and
    # record_call and calls_today only observe. Nothing here gates a call
    # today except the exhaustion marker an upstream 429 sets. Part 3 wires
    # the per-distributor limits and persists the marker across restarts.
    service = PartService(adapters=adapters, quota=QuotaTracker(), disabled=off,
                          timeout_secs=settings.distributor_timeout_secs)
    return service, created
