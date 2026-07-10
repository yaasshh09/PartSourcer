"""Unit tests for the SQLite cache store (dumb storage, no TTL logic)."""

from datetime import datetime, timezone

import pytest

from cache.store import CachedPart, SqliteCacheStore

pytestmark = pytest.mark.anyio

AS_OF = datetime(2026, 7, 10, 12, 0, 0, tzinfo=timezone.utc)
ROW = {"lcsc": "C8734", "mpn": "STM32F103C8T6", "brand": None,
       "package": "LQFP-48(7x7)", "description": "", "stock": 214596,
       "price_usd": 1.0371, "datasheet_url": None,
       "as_of": "2026-07-10T12:00:00+00:00"}
SPECS = {"mpn": "STM32F103C8T6", "brand": None, "package": "LQFP-48(7x7)",
         "description": "", "datasheet_url": None}


@pytest.fixture
def store(tmp_path):
    s = SqliteCacheStore(str(tmp_path / "cache.db"))
    s.open()
    yield s
    s.close()


async def test_search_miss_returns_none(store):
    assert await store.get_search("stm32", 1) is None


async def test_search_round_trip(store):
    await store.put_search("stm32", 1, [ROW], AS_OF)
    got = await store.get_search("stm32", 1)
    assert got is not None
    rows, as_of = got
    assert rows == [ROW]
    assert as_of == AS_OF


async def test_search_key_includes_page(store):
    await store.put_search("stm32", 1, [ROW], AS_OF)
    assert await store.get_search("stm32", 2) is None


async def test_put_search_overwrites(store):
    await store.put_search("stm32", 1, [ROW], AS_OF)
    later = datetime(2026, 7, 10, 15, 0, 0, tzinfo=timezone.utc)
    await store.put_search("stm32", 1, [], later)
    rows, as_of = await store.get_search("stm32", 1)
    assert rows == [] and as_of == later


async def test_part_miss_returns_none(store):
    assert await store.get_part("C8734") is None


async def test_part_round_trip(store):
    await store.upsert_part("C8734", SPECS, 214596, 1.0371, AS_OF, AS_OF)
    p = await store.get_part("C8734")
    assert p == CachedPart(lcsc="C8734", specs=SPECS, specs_as_of=AS_OF,
                           stock=214596, price_usd=1.0371, stock_as_of=AS_OF)


async def test_upsert_part_overwrites(store):
    await store.upsert_part("C8734", SPECS, 214596, 1.0371, AS_OF, AS_OF)
    later = datetime(2026, 7, 10, 15, 0, 0, tzinfo=timezone.utc)
    await store.upsert_part("C8734", SPECS, 100, 0.99, later, later)
    p = await store.get_part("C8734")
    assert p.stock == 100 and p.price_usd == 0.99 and p.stock_as_of == later


async def test_persists_across_reopen(tmp_path):
    path = str(tmp_path / "cache.db")
    s1 = SqliteCacheStore(path)
    s1.open()
    await s1.upsert_part("C8734", SPECS, 214596, 1.0371, AS_OF, AS_OF)
    s1.close()
    s2 = SqliteCacheStore(path)
    s2.open()
    assert (await s2.get_part("C8734")).lcsc == "C8734"
    s2.close()
