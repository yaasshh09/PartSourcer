"""A stand-in CachedPartService for the route tests.

The routes are the unit under test here, so the cache and the distributors
are stubbed out entirely. Cache behaviour has its own tests in
test_cached_search.py and test_cached_lookup.py.
"""

from datetime import datetime, timezone

from models.offer import (DistributorStatus, Offer, Part, SearchResponseV2)

AS_OF = datetime(2026, 8, 14, 9, 0, tzinfo=timezone.utc)


def offer(distributor="lcsc", sku="C8734", mpn="STM32F103C8T6", price=1.04,
          tier="exact"):
    return Offer(distributor=distributor, sku=sku, mpn_as_listed=mpn,
                 match_tier=tier, match_note=None, stock=214596, in_stock=True,
                 price_usd=price, price_breaks=None, currency="USD",
                 product_url=None, as_of=AS_OF)


def part(mpn_key="STM32F103C8T6", offers=None):
    return Part(mpn_key=mpn_key, mpn=mpn_key, brand=None, package="LQFP-48",
                description="ARM MCU", datasheet_url=None,
                offers=list(offers) if offers is not None else [offer()],
                cheapest=None, cheapest_unavailable_reason="only one source")


def status(distributor, state="ok", detail=None):
    return DistributorStatus(distributor=distributor, state=state,
                             detail=detail, as_of=AS_OF if state == "ok" else None)


ALL_OK = [status("lcsc"), status("mouser"), status("digikey")]


class StubCached:
    """Whatever it was handed, returned. Raises `error` instead if given."""

    def __init__(self, found=None, sources=None, canonical=True,
                 skus=None, error=None):
        self._part = found
        self._sources = list(sources) if sources is not None else list(ALL_OK)
        self._canonical = canonical
        self._skus = dict(skus or {})
        self._error = error

    async def search(self, query, page=1, refresh=False) -> SearchResponseV2:
        if self._error is not None:
            raise self._error
        results = [self._part] if self._part is not None else []
        return SearchResponseV2(page=page, query=query, results=results,
                                sources=self._sources)

    async def lookup(self, mpn_key, refresh=False):
        if self._error is not None:
            raise self._error
        return self._part, self._sources, self._canonical

    async def resolve_sku(self, distributor, sku):
        return self._skus.get(sku)


class StubLcsc:
    """Only lookup_sku matters to the routes."""

    name = "lcsc"

    def __init__(self, listings=None):
        self._listings = dict(listings or {})

    async def lookup_sku(self, sku):
        return self._listings.get(sku)
