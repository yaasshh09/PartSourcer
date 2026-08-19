"""What the equivalent matcher needs from LCSC, and nothing else.

The matcher is v1 logic that reasons over LCSC parametric data, and this
sub-project does not change it. It wants get_part and list_parametric, so
this hands it both over LcscAdapter rather than keeping a second jlcsearch
client alive purely to satisfy the shape.
"""

from datetime import datetime, timezone
from typing import Callable

from cache.serde import listing_from_dict, listing_to_dict
from cache.store import CachedOffer, SqliteCacheStore
from models.parametric import ParametricPart
from models.part import PartDetail
from services.adapters.base import RawListing
from services.adapters.lcsc import LcscAdapter
from services.matching import normalize_exact
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

    async def canonical_part(self, mpn: str, lcsc_code: str,
                             allow_cached: bool = True) -> PartDetail | None:
        """The one read whose price and stock are fit to publish.

        Goes through the offer cache first, so the number on an equivalent
        card is the very row the part's own page is serving. Failing that it
        reads upstream the same way and at the same depth the cache is filled
        with. Without a store it is just that upstream read, which is what
        the matcher's own tests use.

        allow_cached=False is for the history recorder. A chart point is
        stamped with the run's time, so it has to be read at that time rather
        than lifted from a row that could be most of a TTL old, and every
        point in the series is then read the same way.
        """
        held = await self._cached(lcsc_code) if allow_cached else None
        if held is not None:
            return held
        listings = await self._adapter.lookup_mpn(mpn, FETCH_DEPTH)
        for listing in listings:
            if listing.sku == lcsc_code:
                await self._remember(listing)
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

    async def _remember(self, listing: RawListing) -> None:
        """Keep what we just quoted, so following the card lands on it.

        A candidate we priced has no row yet, and this query shape is not
        quite the detail page's, so without this the part could cost one
        thing on the card and another on the page it links to. Only reached
        when nothing fresh was held, so it never displaces a live row.
        """
        if self._store is None:
            return
        key = normalize_exact(listing.mpn)
        if not key:
            return
        await self._store.put_offers([CachedOffer(
            listing_key=key, distributor=listing.distributor,
            sku=listing.sku, part_key=key,
            listing=listing_to_dict(listing), as_of=listing.as_of)])

    async def list_parametric(self, category: str, package: str,
                              resistance_ohms: float | None = None
                              ) -> list[ParametricPart]:
        return await self._adapter.list_parametric(category, package,
                                                   resistance_ohms)
