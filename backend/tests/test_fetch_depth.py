"""Every distributor read happens at one fixed depth.

Upstream returns a different price and stock for the same part depending on
how many rows the request asked for (see the live-run findings). The offer
cache is keyed (distributor, sku) with no record of the depth that produced
a row, so two paths reading at different depths overwrite each other and the
app contradicts itself. These tests pin the one thing that prevents it: the
depth never varies.
"""

from datetime import datetime, timezone

import pytest

from cache.cached_part_service import CachedPartService
from cache.store import SqliteCacheStore
from services.adapters.base import DistributorAdapter, RawListing
from services.part_service import FETCH_DEPTH, PartService
from services.quota import QuotaTracker

pytestmark = pytest.mark.anyio

T0 = datetime(2026, 8, 14, 9, 0, tzinfo=timezone.utc)
TTL = 3600
MPNS = ["PART-A", "PART-B", "PART-C"]


class DepthSensitiveAdapter(DistributorAdapter):
    """Stands in for jlcsearch, defect and all.

    The price and stock it reports for a part are a function of the limit it
    was asked for, which is exactly the upstream behaviour that makes a fixed
    depth necessary. It also records every depth it was asked for, so a test
    can assert on the requests rather than only on the answers.
    """

    def __init__(self, name="lcsc", mpns=MPNS):
        self.name = name
        self._mpns = list(mpns)
        self.asked: list[tuple[str, int]] = []

    def _listing(self, mpn: str, limit: int) -> RawListing:
        rank = self._mpns.index(mpn)
        return RawListing(
            distributor=self.name, sku=f"C{rank}", mpn=mpn, brand=None,
            package="0402", description="d", stock=100 * limit, in_stock=True,
            price=round(1.0 + limit / 1000, 4), currency="USD",
            price_breaks=None, datasheet_url=None, product_url=None,
            as_of=T0, rank=rank)

    async def search(self, query, limit):
        self.asked.append(("search", limit))
        return [self._listing(m, limit) for m in self._mpns[:limit]]

    async def lookup_mpn(self, mpn, limit=20):
        self.asked.append(("lookup", limit))
        return [self._listing(m, limit) for m in self._mpns[:limit]]


@pytest.fixture
def store(tmp_path):
    s = SqliteCacheStore(str(tmp_path / "c.db"))
    s.open()
    yield s
    s.close()


def build(store, adapter):
    service = PartService(adapters={adapter.name: adapter},
                          quota=QuotaTracker(), now=lambda: T0)
    return CachedPartService(service=service, store=store,
                             offer_ttl_secs=TTL, now=lambda: T0)


def price_of(parts, mpn_key):
    for part in parts:
        if part.mpn_key == mpn_key:
            return part.offers[0].price_usd
    raise AssertionError(f"{mpn_key} not in {[p.mpn_key for p in parts]}")


async def test_every_read_asks_for_the_same_depth(store):
    """The root cause in one assertion: page number and path must not move it."""
    lcsc = DepthSensitiveAdapter()
    cached = build(store, lcsc)

    await cached.search("stm32", 1)
    await cached.search("stm32", 2)
    await cached.lookup("PART-A")

    assert [limit for _, limit in lcsc.asked] == [FETCH_DEPTH] * len(lcsc.asked)


async def test_requesting_page_two_does_not_change_what_page_one_reports(store):
    """The reproduction from the live run: one user paging changed another's
    price for a part nothing had happened to."""
    cached = build(store, DepthSensitiveAdapter())

    first = await cached.search("stm32", 1)
    await cached.search("stm32", 2)
    again = await cached.search("stm32", 1)

    assert price_of(again.results, "PART-A") == price_of(first.results, "PART-A")


async def test_the_detail_page_agrees_with_the_search_before_it(store):
    """Two surfaces, one part, one number. Both carry an honest as_of, so a
    disagreement here is the app calling itself a liar."""
    cached = build(store, DepthSensitiveAdapter())

    await cached.search("stm32", 2)             # someone pages deeper
    results = await cached.search("stm32", 1)   # what this user is looking at
    part, _sources, _canonical = await cached.lookup("PART-A")

    assert part.offers[0].price_usd == price_of(results.results, "PART-A")
