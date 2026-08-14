"""Registry, fan-out, merge, and status. The layer routes will see.

An adapter knows one distributor. This knows that there are three of them,
that any of them can be missing or broken, and that saying so plainly is
better than a 502 when two of them answered.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
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


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class FanOutResult:
    """Everything one fan-out produced. The cache layer needs all three:
    listings to write through, statuses to record, parts to answer with."""
    listings: list[RawListing]
    statuses: list[DistributorStatus]
    parts: list[Part]


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


def _part_rank(rows: list[tuple[RawListing, str, str | None]]) -> tuple[int, int]:
    """A part's position is its best listing's position, tie-broken by
    canonical distributor order so the answer never depends on which
    distributor happened to answer first."""
    return min((row.rank, ALL_DISTRIBUTORS.index(row.distributor))
               for row, _, _ in rows)


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
                 timeout_secs: float = 8.0,
                 now: Callable[[], datetime] = _utc_now):
        self._adapters = adapters
        self._quota = quota
        self._disabled = dict(disabled or {})
        self._timeout = timeout_secs
        self._now = now

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
                await self._quota.mark_exhausted(name)
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
        # An ok status with no timestamp would make the cache unable to tell
        # "asked, carries nothing" from "never asked", so it would re-ask on
        # every request for a part this distributor genuinely does not stock.
        as_of = min((r.as_of for r in listings), default=self._now())
        return listings, self._status(name, "ok", None, as_of)

    async def fan_out(self, make: Call, only: set[str] | None = None
                      ) -> tuple[list[RawListing], list[DistributorStatus]]:
        statuses: list[DistributorStatus] = []
        pending: list[tuple[str, asyncio.Task]] = []

        for name in ALL_DISTRIBUTORS:
            if only is not None and name not in only:
                continue
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
                # Type only, never the message, for the same reason as the
                # catch-all inside _call_one: a detail we did not compose can
                # carry a connection string or a request URL with a key in it.
                statuses.append(self._status(name, "unavailable",
                                             f"{name} failed: {type(outcome).__name__}"))
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
        for key in sorted(order, key=lambda k: _part_rank(grouped[k])):
            rows = grouped[key]
            offers = [
                Offer(distributor=row.distributor, sku=row.sku,
                      mpn_as_listed=row.mpn, match_tier=tier, match_note=note,
                      stock=row.stock, in_stock=row.in_stock,
                      price_usd=row.price, price_breaks=row.price_breaks,
                      currency=row.currency, product_url=row.product_url,
                      as_of=row.as_of,
                      is_basic=row.is_basic, is_preferred=row.is_preferred)
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

    async def collect(self, make: Call, only: set[str] | None = None
                      ) -> FanOutResult:
        """One fan-out, merged. The single entry point the cache layer uses."""
        listings, statuses = await self.fan_out(make, only=only)
        return FanOutResult(listings=listings, statuses=statuses,
                            parts=self.merge(listings, statuses))

    async def lookup(self, mpn_key: str, limit: int = 20) -> FanOutResult:
        return await self.collect(lambda a: a.lookup_mpn(mpn_key, limit))

    def callable_names(self) -> list[str]:
        """Distributors worth calling right now: present, credentialed, and
        not sitting behind an exhaustion marker."""
        return [n for n in ALL_DISTRIBUTORS
                if n in self._adapters and n not in self._disabled
                and not self._quota.is_exhausted(n)]

    async def search(self, query: str, limit: int,
                     page: int = 1) -> SearchResponseV2:
        # An adapter takes a limit and no offset, so paging happens here:
        # ask upstream for enough rows to reach the page, then window the
        # merged parts locally. Echoing a page number over page-1 results
        # would be a lie.
        want = page * limit
        result = await self.collect(lambda adapter: adapter.search(query, want))
        start = (page - 1) * limit
        return SearchResponseV2(page=page, query=query,
                                results=result.parts[start:start + limit],
                                sources=result.statuses)

    @property
    def timeout_secs(self) -> float:
        return self._timeout

    def adapter_names(self) -> list[str]:
        return [n for n in ALL_DISTRIBUTORS if n in self._adapters]

    def disabled_names(self) -> list[str]:
        return [n for n in ALL_DISTRIBUTORS if n in self._disabled]

    def attach_quota_markers(self, markers, loaded: dict[str, datetime]) -> None:
        """Wire persistence after construction, because deps owns the store
        and the factory does not."""
        self._quota.attach_markers(markers, loaded)


def select_part(parts: list[Part], mpn_key: str) -> tuple[Part | None, bool]:
    """Pick the part a detail request asked for.

    Returns (part, is_canonical). is_canonical False means the request named a
    key that folded into another part, so the caller should redirect to
    part.mpn_key rather than answer under a name the merge does not use.
    """
    for part in parts:
        if part.mpn_key == mpn_key:
            return part, True
    for part in parts:
        for offer in part.offers:
            if normalize_exact(offer.mpn_as_listed) == mpn_key:
                return part, False
    return None, True


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

    # LCSC gets no limit on purpose: jlcsearch publishes no quota, so a number
    # here would be invented. Marker loading and the store wiring happen in
    # deps, which is where the cache store lives.
    limits = {name: limit for name, limit in
              (("mouser", settings.mouser_daily_limit),
               ("digikey", settings.digikey_daily_limit)) if limit is not None}
    service = PartService(adapters=adapters,
                          quota=QuotaTracker(daily_limits=limits),
                          disabled=off,
                          timeout_secs=settings.distributor_timeout_secs)
    return service, created
