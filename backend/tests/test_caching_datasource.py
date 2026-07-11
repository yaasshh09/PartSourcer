"""CachingPartDataSource: freshness split, refresh bypass, as_of honesty."""

from datetime import datetime, timedelta, timezone

import pytest

from cache.caching_datasource import CachingPartDataSource
from cache.store import SqliteCacheStore
from models.part import PartDetail
from models.search import SearchResult
from services.datasource import PartDataSource, UpstreamError

pytestmark = pytest.mark.anyio

T0 = datetime(2026, 7, 10, 12, 0, 0, tzinfo=timezone.utc)
SPECS_TTL = 2_592_000  # 30 days
STOCK_TTL = 3_600      # 1 hour


def result(as_of, stock=214596):
    return SearchResult(lcsc="C8734", mpn="STM32F103C8T6", brand=None,
                        package="LQFP-48(7x7)", description="", stock=stock,
                        price_usd=1.0371, datasheet_url=None, as_of=as_of)


def detail(as_of, stock=214596):
    return PartDetail(lcsc="C8734", mpn="STM32F103C8T6", brand=None,
                      package="LQFP-48(7x7)", description="", stock=stock,
                      price_usd=1.0371, price_breaks=None, stock_breakdown=None,
                      is_basic=False, is_preferred=True, datasheet_url=None,
                      as_of=as_of)


class FakeClock:
    def __init__(self, start=T0):
        self.t = start

    def __call__(self):
        return self.t

    def advance(self, secs):
        self.t += timedelta(seconds=secs)


class FakeDataSource(PartDataSource):
    """Counts calls; returns one canned result stamped with the clock."""

    def __init__(self, clock):
        self.clock = clock
        self.search_calls = 0
        self.get_part_calls = 0
        self.parametric_calls = []
        self._parametric = []

    async def search(self, query, page, refresh=False):
        self.search_calls += 1
        return [result(self.clock())]

    async def get_part(self, lcsc_code, refresh=False):
        self.get_part_calls += 1
        return detail(self.clock())

    async def list_parametric(self, category, package, resistance_ohms=None):
        self.parametric_calls.append((category, package, resistance_ohms))
        return self._parametric


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def inner(clock):
    return FakeDataSource(clock)


@pytest.fixture
def ds(tmp_path, inner, clock):
    store = SqliteCacheStore(str(tmp_path / "cache.db"))
    store.open()
    yield CachingPartDataSource(inner=inner, store=store,
                                specs_ttl_secs=SPECS_TTL,
                                stock_ttl_secs=STOCK_TTL, now=clock)
    store.close()


async def test_search_miss_fetches_and_stores(ds, inner):
    got = await ds.search("STM32", 1)
    assert inner.search_calls == 1
    assert got == [result(T0)]


async def test_search_hit_skips_inner_and_keeps_as_of(ds, inner, clock):
    await ds.search("STM32", 1)
    clock.advance(600)  # 10 min later, still < stock TTL
    got = await ds.search("STM32", 1)
    assert inner.search_calls == 1          # served from cache
    assert got[0].as_of == T0               # stored fetch time, not now


async def test_search_query_normalized_for_cache_key(ds, inner):
    await ds.search("STM32", 1)
    await ds.search("  stm32  ", 1)
    assert inner.search_calls == 1


async def test_search_stale_refetches(ds, inner, clock):
    await ds.search("STM32", 1)
    clock.advance(STOCK_TTL + 1)
    got = await ds.search("STM32", 1)
    assert inner.search_calls == 2
    assert got[0].as_of == clock()


async def test_search_refresh_bypasses_fresh_cache(ds, inner, clock):
    await ds.search("STM32", 1)
    clock.advance(60)
    got = await ds.search("STM32", 1, refresh=True)
    assert inner.search_calls == 2
    assert got[0].as_of == clock()


async def test_empty_query_never_touches_cache_or_inner(ds, inner):
    assert await ds.search("   ", 1) == []
    assert inner.search_calls == 0


async def test_empty_results_are_cached(ds, inner, clock):
    async def empty_search(query, page, refresh=False):
        inner.search_calls += 1
        return []
    inner.search = empty_search
    await ds.search("zzzznope", 1)
    await ds.search("zzzznope", 1)
    assert inner.search_calls == 1


async def test_get_part_miss_fetches_and_stores(ds, inner):
    got = await ds.get_part("C8734")
    assert inner.get_part_calls == 1
    assert got == detail(T0)


async def test_get_part_hit_skips_inner_and_keeps_as_of(ds, inner, clock):
    await ds.get_part("C8734")
    clock.advance(600)
    got = await ds.get_part("C8734")
    assert inner.get_part_calls == 1
    assert got.as_of == T0


async def test_get_part_normalizes_code_for_cache_key(ds, inner):
    await ds.get_part("C8734")
    await ds.get_part("8734")
    await ds.get_part("c8734")
    assert inner.get_part_calls == 1


async def test_get_part_stale_stock_refetches(ds, inner, clock):
    await ds.get_part("C8734")
    clock.advance(STOCK_TTL + 1)
    got = await ds.get_part("C8734")
    assert inner.get_part_calls == 2
    assert got.as_of == clock()


async def test_get_part_refresh_bypasses_fresh_cache(ds, inner, clock):
    await ds.get_part("C8734")
    clock.advance(60)
    got = await ds.get_part("C8734", refresh=True)
    assert inner.get_part_calls == 2
    assert got.as_of == clock()


async def test_get_part_none_is_returned_without_caching(ds, inner):
    async def missing(lcsc_code, refresh=False):
        inner.get_part_calls += 1
        return None
    inner.get_part = missing
    assert await ds.get_part("C0") is None
    assert await ds.get_part("C0") is None
    assert inner.get_part_calls == 2        # a miss is never cached


async def test_search_warmed_row_is_incomplete_so_detail_fetches_flags(ds, inner):
    # Search write-through stores no flags; get_part must re-fetch to fill them.
    await ds.search("STM32", 1)
    got = await ds.get_part("C8734")
    assert inner.get_part_calls == 1
    assert got.is_basic is False and got.is_preferred is True


async def test_get_part_complete_row_hits_cache(ds, inner, clock):
    await ds.get_part("C8734")            # miss -> fetch -> stores flags
    clock.advance(600)                    # still < stock TTL
    got = await ds.get_part("C8734")
    assert inner.get_part_calls == 1      # complete row served from cache
    assert got.as_of == T0
    assert got.is_basic is False and got.is_preferred is True


async def test_stale_cache_never_softens_upstream_failure(ds, inner, clock):
    """§5 honesty: stale entry + upstream down → error, never stale stock."""
    await ds.search("STM32", 1)
    clock.advance(STOCK_TTL + 1)

    async def failing(query, page, refresh=False):
        raise UpstreamError("unavailable", "down")
    inner.search = failing
    with pytest.raises(UpstreamError):
        await ds.search("STM32", 1)


async def test_list_parametric_passthrough_not_cached(ds, inner):
    inner._parametric = ["sentinel"]
    out1 = await ds.list_parametric("resistors", "0603", resistance_ohms=10000)
    out2 = await ds.list_parametric("resistors", "0603", resistance_ohms=10000)
    assert out1 == ["sentinel"] and out2 == ["sentinel"]
    # Uncached in v1: inner is hit every time.
    assert inner.parametric_calls == [
        ("resistors", "0603", 10000), ("resistors", "0603", 10000)]


async def test_get_part_stale_plus_upstream_failure_propagates(clock, tmp_path):
    from cache.store import SqliteCacheStore
    store = SqliteCacheStore(str(tmp_path / "c.db"))
    store.open()
    # Warm a complete part row at T0.
    warm = CachingPartDataSource(FakeDataSource(clock), store,
                                 SPECS_TTL, STOCK_TTL, now=clock)
    await warm.get_part("C8734")
    clock.advance(STOCK_TTL + 1)  # stock row now stale

    class Boom(PartDataSource):
        async def search(self, q, page, refresh=False):
            raise UpstreamError("unavailable", "down")
        async def get_part(self, code, refresh=False):
            raise UpstreamError("unavailable", "down")
        async def list_parametric(self, category, package, resistance_ohms=None):
            return []

    ds = CachingPartDataSource(Boom(), store, SPECS_TTL, STOCK_TTL, now=clock)
    with pytest.raises(UpstreamError):  # never stale-serve
        await ds.get_part("C8734")
    store.close()


async def test_ttl_exact_boundary_is_not_fresh(clock, tmp_path):
    from cache.store import SqliteCacheStore
    store = SqliteCacheStore(str(tmp_path / "c.db"))
    store.open()
    inner = FakeDataSource(clock)
    ds = CachingPartDataSource(inner, store, SPECS_TTL, STOCK_TTL, now=clock)
    await ds.search("stm32", 1)            # cached at T0, search_calls == 1
    clock.advance(STOCK_TTL)               # exactly at the boundary
    await ds.search("stm32", 1)            # strict < ttl -> not fresh -> refetch
    assert inner.search_calls == 2
    store.close()


async def test_refresh_throttled_degrades_to_cache(clock, tmp_path):
    from cache.store import SqliteCacheStore
    from services.throttle import RefreshThrottle

    class FakeMono:
        def __init__(self):
            self.t = 0.0

        def __call__(self):
            return self.t

        def advance(self, secs):
            self.t += secs

    mono = FakeMono()
    store = SqliteCacheStore(str(tmp_path / "c.db"))
    store.open()
    inner = FakeDataSource(clock)
    ds = CachingPartDataSource(inner, store, SPECS_TTL, STOCK_TTL,
                               now=clock, throttle=RefreshThrottle(10, now=mono))
    await ds.search("stm32", 1)                       # miss -> fetch (calls==1)
    await ds.search("stm32", 1, refresh=True)         # 1st refresh allowed (==2)
    await ds.search("stm32", 1, refresh=True)         # throttled -> cache (==2)
    assert inner.search_calls == 2
    mono.advance(11)
    await ds.search("stm32", 1, refresh=True)         # cooldown elapsed (==3)
    assert inner.search_calls == 3
    store.close()
