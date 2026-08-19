"""Unit tests for the SQLite cache store, v2 (dumb storage, no TTL logic)."""

import sqlite3
from datetime import datetime, timezone

import pytest

from cache.store import CACHE_SCHEMA_VERSION, CachedOffer, SqliteCacheStore

pytestmark = pytest.mark.anyio

AS_OF = datetime(2026, 8, 14, 9, 14, tzinfo=timezone.utc)


@pytest.fixture
def store(tmp_path):
    s = SqliteCacheStore(str(tmp_path / "c.db"))
    s.open()
    yield s
    s.close()


def offer(listing_key="PART-A", distributor="lcsc", sku="C1", part_key=None):
    return CachedOffer(listing_key=listing_key, distributor=distributor,
                       sku=sku, part_key=part_key or listing_key,
                       listing={"mpn": listing_key}, as_of=AS_OF)


async def test_offers_round_trip_by_part_key(store):
    await store.put_offers([offer(), offer("PART-A-TR", "mouser", "M1", "PART-A")])

    got = await store.get_offers(["PART-A"])

    assert {o.sku for o in got} == {"C1", "M1"}
    assert got[0].as_of == AS_OF


async def test_put_offers_replaces_a_listing_in_place(store):
    await store.put_offers([offer()])
    updated = offer()
    updated.listing = {"mpn": "PART-A", "price": 1.5}
    await store.put_offers([updated])

    got = await store.get_offers(["PART-A"])

    assert len(got) == 1 and got[0].listing["price"] == 1.5


async def test_search_row_round_trips(store):
    await store.put_search("stm32", 20, ["PART-A", "PART-B"],
                           [{"distributor": "lcsc", "state": "ok"}], AS_OF)

    row = await store.get_search("stm32")

    assert row.limit_used == 20
    assert row.part_keys == ["PART-A", "PART-B"]
    assert row.statuses[0]["state"] == "ok"
    assert row.as_of == AS_OF
    assert await store.get_search("nothing") is None


async def test_part_status_row_round_trips(store):
    await store.put_part_status("PART-A",
                                [{"distributor": "lcsc", "state": "ok"}], AS_OF)

    row = await store.get_part_status("PART-A")

    assert row.statuses[0]["distributor"] == "lcsc"
    assert await store.get_part_status("PART-B") is None


async def test_find_part_key_by_sku_powers_the_legacy_redirect(store):
    await store.put_offers([offer("STM32F103C8T6", "lcsc", "C8734")])

    assert await store.find_part_key_by_sku("lcsc", "C8734") == "STM32F103C8T6"
    assert await store.find_part_key_by_sku("lcsc", "C9999") is None


async def test_quota_markers_round_trip(store):
    await store.put_quota_marker("mouser", AS_OF)

    assert await store.get_quota_markers() == {"mouser": AS_OF}


async def test_a_v1_database_is_dropped_and_rebuilt(tmp_path):
    """The cache holds no source of truth, so rebuilding is free and correct."""
    path = str(tmp_path / "old.db")
    conn = sqlite3.connect(path)
    conn.executescript(
        "CREATE TABLE parts (lcsc TEXT PRIMARY KEY, specs_json TEXT);"
        "INSERT INTO parts VALUES ('C8734', '{}');")
    conn.commit()
    conn.close()

    s = SqliteCacheStore(path)
    s.open()
    try:
        with sqlite3.connect(path) as check:
            names = {r[0] for r in check.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            version = check.execute("SELECT version FROM schema_meta").fetchone()[0]
    finally:
        s.close()

    assert "parts" not in names
    assert {"offers", "search_cache", "part_cache", "quota_state"} <= names
    assert version == CACHE_SCHEMA_VERSION


async def test_opening_a_current_database_twice_keeps_its_rows(tmp_path):
    path = str(tmp_path / "c.db")
    first = SqliteCacheStore(path)
    first.open()
    await first.put_offers([offer()])
    first.close()

    second = SqliteCacheStore(path)
    second.open()
    try:
        assert len(await second.get_offers(["PART-A"])) == 1
    finally:
        second.close()


async def test_prune_drops_rows_too_old_to_serve(store):
    """Nothing evicts on its own, so on a deploy with a real volume the cache
    grows forever. A row past the freshness gates can never be returned."""
    from datetime import timedelta
    from cache.store import CachedOffer

    old = AS_OF - timedelta(days=30)
    await store.put_offers([
        CachedOffer(listing_key="OLD", distributor="lcsc", sku="C1",
                    part_key="OLD", listing={"mpn": "OLD"}, as_of=old),
        CachedOffer(listing_key="NEW", distributor="lcsc", sku="C2",
                    part_key="NEW", listing={"mpn": "NEW"}, as_of=AS_OF),
    ])
    await store.put_search("stale", 40, ["OLD"], [], old)
    await store.put_search("fresh", 40, ["NEW"], [], AS_OF)
    await store.put_part_status("OLD", [], old)
    await store.put_parametric("resistors|0603|", [{"lcsc": "C1"}], old)

    dropped = await store.prune(AS_OF - timedelta(days=7))

    assert dropped == 4
    assert [o.listing_key for o in await store.get_offers(["OLD", "NEW"])] == ["NEW"]
    assert await store.get_search("stale") is None
    assert await store.get_search("fresh") is not None
    assert await store.get_part_status("OLD") is None
    assert await store.get_parametric("resistors|0603|") is None


async def test_prune_on_an_empty_cache_is_a_no_op(store):
    from datetime import timedelta
    assert await store.prune(AS_OF - timedelta(days=7)) == 0
