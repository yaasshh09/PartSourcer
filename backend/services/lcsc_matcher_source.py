"""What the equivalent matcher needs from LCSC, and nothing else.

The matcher is v1 logic that reasons over LCSC parametric data, and this
sub-project does not change it. It wants get_part and list_parametric, so
this hands it both over LcscAdapter rather than keeping a second jlcsearch
client alive purely to satisfy the shape.
"""

from datetime import datetime, timezone
from typing import Callable

from cache.serde import listing_from_dict
from cache.store import SqliteCacheStore
from models.parametric import ParametricPart
from models.part import PartDetail
from services.adapters.base import RawListing
from services.adapters.lcsc import LcscAdapter
from services.part_service import FETCH_DEPTH


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_detail(listing: RawListing) -> PartDetail:
    return PartDetail(
        lcsc=listing.sku, mpn=listing.mpn, brand=listing.brand,
        package=listing.package, description=listing.description,
        stock=listing.stock, price_usd=listing.price,
        price_breaks=listing.price_breaks, stock_breakdown=None,
        is_basic=listing.is_basic, is_preferred=listing.is_preferred,
        datasheet_url=listing.datasheet_url, as_of=listing.as_of)


class LcscMatcherSource:
    def __init__(self, adapter: LcscAdapter,
                 store: SqliteCacheStore | None = None,
                 offer_ttl_secs: int = 0,
                 now: Callable[[], datetime] = _utc_now):
        self._adapter = adapter
        self._store = store
        self._ttl = offer_ttl_secs
        self._now = now

    def _fresh(self, as_of: datetime) -> bool:
        return (self._now() - as_of).total_seconds() < self._ttl

    async def get_part(self, lcsc_code: str,
                       refresh: bool = False) -> PartDetail | None:
        """Resolve a bare LCSC code to a part.

        This is the only way to go from a code to an MPN, so it stays, but
        its query shape is its own and upstream prices differ by query shape.
        Callers take the identity from here and the numbers from
        canonical_part.
        """
        listing = await self._adapter.lookup_sku(lcsc_code)
        return None if listing is None else _to_detail(listing)

    async def canonical_part(self, mpn: str,
                             lcsc_code: str) -> PartDetail | None:
        """The one read whose price and stock are fit to publish.

        Goes through the offer cache first, so the number on an equivalent
        card is the very row the part's own page is serving. Failing that it
        reads upstream the same way and at the same depth the cache is filled
        with. Without a store it is just that upstream read, which is what
        the matcher's own tests use.
        """
        held = await self._cached(lcsc_code)
        if held is not None:
            return held
        listings = await self._adapter.lookup_mpn(mpn, FETCH_DEPTH)
        for listing in listings:
            if listing.sku == lcsc_code:
                return _to_detail(listing)
        return None

    async def _cached(self, lcsc_code: str) -> PartDetail | None:
        if self._store is None:
            return None
        rows = await self._store.get_offers_by_sku([("lcsc", lcsc_code)])
        for row in rows:
            if self._fresh(row.as_of):
                return _to_detail(listing_from_dict(row.listing))
        return None

    async def list_parametric(self, category: str, package: str,
                              resistance_ohms: float | None = None
                              ) -> list[ParametricPart]:
        return await self._adapter.list_parametric(category, package,
                                                   resistance_ohms)
