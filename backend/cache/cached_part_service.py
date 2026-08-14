"""Freshness decisions for the multi-distributor service layer.

PartService knows how to ask three distributors and merge what they say.
This knows which of them still needs asking. A source that answered is
served from its cached listings; a source that was missing, errored, or has
gone stale is re-attempted and merged in. That is the partial hit, and it is
why per-distributor status is stored alongside the results.

Never stale-serves. Cached listings carry their own as_of, and Part.as_of is
the oldest of them, so a repaired response can never look fresher than its
stalest component.
"""

import logging
from datetime import datetime, timezone
from typing import Callable, Iterable

from cache.serde import listing_from_dict, listing_to_dict
from cache.store import CachedOffer, SqliteCacheStore
from models.offer import DistributorStatus, Part, SearchResponseV2
from services.adapters.base import RawListing
from services.matching import normalize_exact
from services.part_service import ALL_DISTRIBUTORS, PartService, select_part
from services.throttle import RefreshThrottle

PAGE_SIZE = 20

log = logging.getLogger("partsourcer.cache")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _spine_order(parts: list[Part], spine: list[str]) -> list[Part]:
    """Cached order first, newly seen keys appended.

    A repair that discovers new parts must not shift the ones already shown,
    or page 2 grows duplicates and gaps for a user mid-session.
    """
    position = {key: i for i, key in enumerate(spine)}
    return sorted(parts,
                  key=lambda p: (position.get(p.mpn_key, len(position)),))


class CachedPartService:
    def __init__(self, service: PartService, store: SqliteCacheStore,
                 offer_ttl_secs: int,
                 now: Callable[[], datetime] = _utc_now,
                 throttle: RefreshThrottle | None = None):
        self._service = service
        self._store = store
        self._ttl = offer_ttl_secs
        self._now = now
        self._throttle = throttle

    # -- freshness --

    def _fresh(self, as_of: datetime) -> bool:
        return (self._now() - as_of).total_seconds() < self._ttl

    def _cached_ok(self, statuses: list[dict]) -> set[str]:
        """Distributors whose cached answer is both ok and still fresh."""
        out: set[str] = set()
        for status in statuses:
            if status.get("state") != "ok" or not status.get("as_of"):
                continue
            if self._fresh(datetime.fromisoformat(status["as_of"])):
                out.add(status["distributor"])
        return out

    def _retry_set(self, statuses: list[dict], key: str,
                   refresh: bool) -> tuple[set[str], set[str]]:
        """Returns (served_from_cache, to_retry).

        A cached `disabled` for a distributor that now has credentials lands
        in the retry set, which is right: it was never contacted, so there is
        nothing to serve.
        """
        cached_ok = self._cached_ok(statuses)
        callable_now = set(self._service.callable_names())
        if not refresh:
            return cached_ok, callable_now - cached_ok
        # A throttled refresh falls back to cached data for that distributor
        # only, rather than denying the whole request.
        retry = {name for name in callable_now
                 if self._throttle is None or self._throttle.allow(name, key)}
        return cached_ok - retry, retry

    # -- reconstitution and write-through --

    async def _cached_listings(self, part_keys: list[str],
                               served: set[str]) -> list[RawListing]:
        rows = await self._store.get_offers(part_keys)
        return [listing_from_dict(row.listing) for row in rows
                if row.distributor in served]

    async def _write_offers(self, listings: Iterable[RawListing],
                            parts: list[Part]) -> None:
        """Store the listings under the part key the merge just assigned.

        part_key is only a retrieval index. The merge runs again on every read
        and re-derives the fold from scratch, so a key that moves is not a
        stale claim.
        """
        part_of = {normalize_exact(offer.mpn_as_listed): part.mpn_key
                   for part in parts for offer in part.offers}
        rows = []
        for listing in listings:
            listing_key = normalize_exact(listing.mpn)
            if not listing_key:
                continue
            rows.append(CachedOffer(
                listing_key=listing_key, distributor=listing.distributor,
                sku=listing.sku, part_key=part_of.get(listing_key, listing_key),
                listing=listing_to_dict(listing), as_of=listing.as_of))
        await self._store.put_offers(rows)

    def _log_sources(self, statuses: list[DistributorStatus]) -> None:
        """One line per distributor outcome. Never the detail: an unmapped
        failure's detail is a type name today, but keeping details out of logs
        entirely means there is one rule to check rather than two."""
        for status in statuses:
            log.info("source=%s state=%s", status.distributor, status.state)

    def _merge_statuses(self, cached: list[dict],
                        fresh: list[DistributorStatus]) -> list[DistributorStatus]:
        by_name = {s["distributor"]: DistributorStatus.model_validate(s)
                   for s in cached}
        by_name.update({s.distributor: s for s in fresh})
        return sorted(by_name.values(),
                      key=lambda s: ALL_DISTRIBUTORS.index(s.distributor))

    # -- the search path --

    async def search(self, query: str, page: int = 1,
                     refresh: bool = False) -> SearchResponseV2:
        key = query.strip().lower()
        if not key:
            return SearchResponseV2(page=page, query=query, results=[],
                                    sources=[])

        want = page * PAGE_SIZE
        row = await self._store.get_search(key)

        # Gate 1: a row past the offer TTL is discarded whole, so a part that
        # newly appeared upstream is still discoverable.
        if (row is None or not self._fresh(row.as_of)
                or row.limit_used < want):
            log.info("search miss q=%r page=%d depth=%d", key, page, want)
            result = await self._service.collect(
                lambda adapter: adapter.search(query, want))
            await self._store.put_search(
                key, want, [p.mpn_key for p in result.parts],
                [s.model_dump(mode="json") for s in result.statuses],
                self._now())
            await self._write_offers(result.listings, result.parts)
            self._log_sources(result.statuses)
            return self._window(query, page, result.parts, result.statuses)

        served, retry = self._retry_set(row.statuses, f"search:{key}", refresh)
        cached_listings = await self._cached_listings(row.part_keys, served)

        if not retry:
            log.info("search hit q=%r page=%d served=%s", key, page,
                     sorted(served))
            statuses = [DistributorStatus.model_validate(s) for s in row.statuses]
            self._log_sources(statuses)
            parts = _spine_order(self._service.merge(cached_listings, statuses),
                                 row.part_keys)
            return self._window(query, page, parts, statuses)

        log.info("search partial q=%r page=%d served=%s retry=%s", key, page,
                 sorted(served), sorted(retry))
        result = await self._service.collect(
            lambda adapter: adapter.search(query, row.limit_used), only=retry)
        statuses = self._merge_statuses(row.statuses, result.statuses)
        self._log_sources(statuses)
        parts = _spine_order(
            self._service.merge(cached_listings + result.listings, statuses),
            row.part_keys)
        await self._store.put_search(
            key, row.limit_used, [p.mpn_key for p in parts],
            [s.model_dump(mode="json") for s in statuses], self._now())
        await self._write_offers(result.listings, parts)
        return self._window(query, page, parts, statuses)

    # -- the detail path --

    async def lookup(self, mpn_key: str, refresh: bool = False
                     ) -> tuple[Part | None, list[DistributorStatus], bool]:
        """Resolve one part. Returns (part, sources, is_canonical).

        is_canonical False means the request named a key that folds into
        another part, so the caller should redirect rather than answer under
        a name the merge does not use.
        """
        row = await self._store.get_part_status(mpn_key)

        if row is None or not self._fresh(row.as_of):
            log.info("lookup miss key=%s", mpn_key)
            result = await self._service.lookup(mpn_key)
            await self._commit_lookup(mpn_key, result.listings, result.parts,
                                      result.statuses)
            self._log_sources(result.statuses)
            part, canonical = select_part(result.parts, mpn_key)
            return part, result.statuses, canonical

        served, retry = self._retry_set(row.statuses, f"part:{mpn_key}", refresh)
        cached_listings = await self._cached_listings([mpn_key], served)

        if not retry:
            log.info("lookup hit key=%s served=%s", mpn_key, sorted(served))
            statuses = [DistributorStatus.model_validate(s) for s in row.statuses]
            self._log_sources(statuses)
            parts = self._service.merge(cached_listings, statuses)
            part, canonical = select_part(parts, mpn_key)
            return part, statuses, canonical

        log.info("lookup partial key=%s served=%s retry=%s", mpn_key,
                 sorted(served), sorted(retry))
        result = await self._service.collect(
            lambda adapter: adapter.lookup_mpn(mpn_key), only=retry)
        statuses = self._merge_statuses(row.statuses, result.statuses)
        self._log_sources(statuses)
        parts = self._service.merge(cached_listings + result.listings, statuses)
        await self._commit_lookup(mpn_key, result.listings, parts, statuses)
        part, canonical = select_part(parts, mpn_key)
        return part, statuses, canonical

    async def _commit_lookup(self, mpn_key: str, listings: list[RawListing],
                             parts: list[Part],
                             statuses: list[DistributorStatus]) -> None:
        # Offers for every listing, including parts the keyword lookup dragged
        # in: that is free cache warming. A status row only for the key we
        # actually asked about, because that is the only question we asked.
        await self._write_offers(listings, parts)
        await self._store.put_part_status(
            mpn_key, [s.model_dump(mode="json") for s in statuses], self._now())

    async def resolve_sku(self, distributor: str, sku: str) -> str | None:
        """A distributor SKU to its part key, for the legacy redirect."""
        return await self._store.find_part_key_by_sku(distributor, sku)

    def _window(self, query: str, page: int, parts: list[Part],
                statuses: list[DistributorStatus]) -> SearchResponseV2:
        start = (page - 1) * PAGE_SIZE
        return SearchResponseV2(page=page, query=query,
                                results=parts[start:start + PAGE_SIZE],
                                sources=statuses)
