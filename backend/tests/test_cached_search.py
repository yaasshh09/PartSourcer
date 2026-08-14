from datetime import datetime, timedelta, timezone

import pytest

from cache.cached_part_service import PAGE_SIZE, CachedPartService
from cache.store import SqliteCacheStore
from services.adapters.base import DistributorAdapter, RawListing, UpstreamError
from services.part_service import PartService
from services.quota import QuotaTracker

pytestmark = pytest.mark.anyio

T0 = datetime(2026, 8, 14, 9, 0, tzinfo=timezone.utc)
TTL = 3600


class CountingAdapter(DistributorAdapter):
    def __init__(self, name, mpns, as_of=T0, fail=None):
        self.name = name
        self._mpns = mpns
        self._as_of = as_of
        self._fail = fail
        self.calls = 0

    def _listing(self, mpn, rank):
        return RawListing(distributor=self.name, sku=f"{self.name[:1].upper()}{rank}",
                          mpn=mpn, brand=None, package="P", description="d",
                          stock=100, in_stock=True, price=1.0, currency="USD",
                          price_breaks=None, datasheet_url=None,
                          product_url=None, as_of=self._as_of, rank=rank)

    async def search(self, query, limit):
        self.calls += 1
        if self._fail:
            raise UpstreamError(self._fail, f"{self.name} broke")
        return [self._listing(m, i) for i, m in enumerate(self._mpns[:limit])]

    async def lookup_mpn(self, mpn, limit=20):
        return await self.search(mpn, limit)


@pytest.fixture
def store(tmp_path):
    s = SqliteCacheStore(str(tmp_path / "c.db"))
    s.open()
    yield s
    s.close()


def build(store, adapters, now=lambda: T0):
    service = PartService(adapters=adapters, quota=QuotaTracker(), now=now)
    return CachedPartService(service=service, store=store,
                             offer_ttl_secs=TTL, now=now)


async def test_a_full_hit_makes_no_calls(store):
    lcsc = CountingAdapter("lcsc", ["PART-A", "PART-B"])
    mouser = CountingAdapter("mouser", ["PART-A"])
    cached = build(store, {"lcsc": lcsc, "mouser": mouser})

    first = await cached.search("stm32", 1)
    second = await cached.search("stm32", 1)

    assert lcsc.calls == 1 and mouser.calls == 1
    assert [p.mpn_key for p in second.results] == [p.mpn_key for p in first.results]


async def test_a_failed_source_is_re_attempted_and_merged_in(store):
    """The whole point: LCSC answered, Mouser did not, so only Mouser is
    called again and its offers join the ones already cached."""
    lcsc = CountingAdapter("lcsc", ["PART-A"])
    broken = CountingAdapter("mouser", ["PART-A"], fail="unavailable")
    cached = build(store, {"lcsc": lcsc, "mouser": broken})
    await cached.search("stm32", 1)

    broken._fail = None
    result = await cached.search("stm32", 1)

    assert lcsc.calls == 1          # served from cache
    assert broken.calls == 2        # re-attempted
    assert {o.distributor for o in result.results[0].offers} == {"lcsc", "mouser"}
    assert [s.state for s in result.sources if s.distributor == "mouser"] == ["ok"]


async def test_a_row_past_the_ttl_re_fans_out_so_new_parts_appear(store):
    lcsc = CountingAdapter("lcsc", ["PART-A"])
    clock = {"t": T0}
    cached = build(store, {"lcsc": lcsc}, now=lambda: clock["t"])
    await cached.search("stm32", 1)

    clock["t"] = T0 + timedelta(seconds=TTL + 1)
    await cached.search("stm32", 1)

    assert lcsc.calls == 2


async def test_a_stale_ok_status_inside_a_fresh_row_is_re_attempted(store):
    """Gate 2 is not implied by gate 1: a repair rewrites the row's as_of
    while carrying older per-distributor statuses forward."""
    old = CountingAdapter("lcsc", ["PART-A"], as_of=T0 - timedelta(seconds=TTL + 1))
    cached = build(store, {"lcsc": old})
    await cached.search("stm32", 1)

    await cached.search("stm32", 1)

    assert old.calls == 2


async def test_a_page_two_request_against_a_page_one_row_misses(store):
    lcsc = CountingAdapter("lcsc", [f"PART-{i}" for i in range(PAGE_SIZE * 2)])
    cached = build(store, {"lcsc": lcsc})
    await cached.search("stm32", 1)

    page2 = await cached.search("stm32", 2)

    assert lcsc.calls == 2
    assert len(page2.results) == PAGE_SIZE
    assert page2.results[0].mpn_key == f"PART-{PAGE_SIZE}"


async def test_page_one_is_still_served_from_the_deeper_row(store):
    lcsc = CountingAdapter("lcsc", [f"PART-{i}" for i in range(PAGE_SIZE * 2)])
    cached = build(store, {"lcsc": lcsc})
    await cached.search("stm32", 2)

    page1 = await cached.search("stm32", 1)

    assert lcsc.calls == 1
    assert page1.results[0].mpn_key == "PART-0"


async def test_a_repair_appends_new_keys_instead_of_reordering(store):
    """Pagination must stay stable across a repair, or a user paging through
    results sees duplicates and gaps."""
    lcsc = CountingAdapter("lcsc", ["PART-A", "PART-B"])
    broken = CountingAdapter("mouser", ["PART-NEW"], fail="unavailable")
    cached = build(store, {"lcsc": lcsc, "mouser": broken})
    await cached.search("stm32", 1)

    broken._fail = None
    result = await cached.search("stm32", 1)

    assert [p.mpn_key for p in result.results] == ["PART-A", "PART-B", "PART-NEW"]


async def test_an_empty_query_asks_nothing(store):
    lcsc = CountingAdapter("lcsc", ["PART-A"])
    cached = build(store, {"lcsc": lcsc})

    result = await cached.search("   ", 1)

    assert result.results == [] and result.sources == [] and lcsc.calls == 0
