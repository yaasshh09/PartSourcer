"""One suite, both cache stores.

Anything true of "a cache" rather than "a SQLite file" lives here and runs
against every implementation, so the Postgres store cannot quietly drift from
the SQLite one it replaces on a multi instance host. Storage specific things
(rebuilding a v1 file, reopening the same path) stay in test_cache_store.py.

The Postgres parameter is marked live and deselected by default. Run it with:

    pytest -m live tests/test_cache_store_contract.py

and point TEST_PG_DSN at a throwaway database. It is deliberately NOT read
from DATABASE_URL: these tests empty every cache_ table between cases, and
that variable normally holds the real one.
"""

import inspect
import os
from datetime import datetime, timedelta, timezone

import pytest

from cache.pg_store import _TABLES, PostgresCacheStore
from cache.store import CACHE_SCHEMA_VERSION, CachedOffer, SqliteCacheStore

pytestmark = pytest.mark.anyio

AS_OF = datetime(2026, 8, 14, 9, 14, tzinfo=timezone.utc)


def offer(listing_key="PART-A", distributor="lcsc", sku="C1", part_key=None,
          as_of=AS_OF):
    return CachedOffer(listing_key=listing_key, distributor=distributor,
                       sku=sku, part_key=part_key or listing_key,
                       listing={"mpn": listing_key}, as_of=as_of)


async def _empty(store: PostgresCacheStore) -> None:
    async with store._pool.acquire() as conn:
        for table in _TABLES:
            if table != "cache_schema_meta":
                await conn.execute(f"DELETE FROM {table}")


@pytest.fixture(params=[
    "sqlite",
    pytest.param("postgres", marks=pytest.mark.live),
])
async def store(request, tmp_path):
    if request.param == "sqlite":
        s = SqliteCacheStore(str(tmp_path / "c.db"))
        s.open()
        yield s
        s.close()
        return
    dsn = os.environ.get("TEST_PG_DSN")
    if not dsn:
        pytest.skip("set TEST_PG_DSN to a throwaway database")
    s = PostgresCacheStore(dsn)
    await s.open()
    await _empty(s)
    try:
        yield s
    finally:
        await s.close()


async def _close(store) -> None:
    """SQLite closes a file synchronously, Postgres closes a pool."""
    closed = store.close()
    if inspect.isawaitable(closed):
        await closed


@pytest.fixture(params=[
    "sqlite",
    pytest.param("postgres", marks=pytest.mark.live),
])
async def open_store(request, tmp_path):
    """Opens a cache at one fixed location, as often as a test asks.

    Reopening is what a deployment actually does. Every cold start opens the
    same database again, so the second open has to be as safe as the first and
    has to leave the rows alone.
    """
    opened = []

    async def _open():
        if request.param == "sqlite":
            store = SqliteCacheStore(str(tmp_path / "c.db"))
            store.open()
        else:
            dsn = os.environ.get("TEST_PG_DSN")
            if not dsn:
                pytest.skip("set TEST_PG_DSN to a throwaway database")
            store = PostgresCacheStore(dsn)
            await store.open()
            if not opened:
                await _empty(store)
        opened.append(store)
        return store

    yield _open
    for store in reversed(opened):
        await _close(store)


async def test_opening_the_same_cache_again_keeps_what_is_stored(open_store):
    first = await open_store()
    await first.put_offers([offer()])
    await _close(first)

    second = await open_store()

    got = await second.get_offers(["PART-A"])
    assert len(got) == 1 and got[0].sku == "C1"


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


async def test_put_offers_takes_the_last_row_when_one_batch_repeats_a_key(store):
    """One fan-out can hand us the same offer twice.

    Two distributor reads can land on the same (listing_key, distributor, sku)
    inside a single write, so the batch has to settle on one row the same way
    two separate writes would: the last one wins.
    """
    first = offer()
    first.listing = {"mpn": "PART-A", "price": 9.0}
    last = offer()
    last.listing = {"mpn": "PART-A", "price": 1.5}

    await store.put_offers([first, last])

    got = await store.get_offers(["PART-A"])
    assert len(got) == 1 and got[0].listing["price"] == 1.5


async def test_a_replaced_offer_can_move_to_a_new_part_key(store):
    """part_key is where the last merge filed the row, and merges move."""
    await store.put_offers([offer(part_key="PART-A")])
    await store.put_offers([offer(part_key="PART-Z")])

    assert await store.get_offers(["PART-A"]) == []
    assert len(await store.get_offers(["PART-Z"])) == 1


async def test_search_row_round_trips(store):
    await store.put_search("stm32", 20, ["PART-A", "PART-B"],
                           [{"distributor": "lcsc", "state": "ok"}], AS_OF)

    row = await store.get_search("stm32")

    assert row.limit_used == 20
    assert row.part_keys == ["PART-A", "PART-B"]
    assert row.statuses[0]["state"] == "ok"
    assert row.as_of == AS_OF
    assert await store.get_search("nothing") is None


async def test_a_second_put_search_replaces_the_first(store):
    await store.put_search("stm32", 20, ["OLD"], [], AS_OF)
    await store.put_search("stm32", 40, ["NEW"], [], AS_OF)

    row = await store.get_search("stm32")

    assert row.limit_used == 40 and row.part_keys == ["NEW"]


async def test_part_status_row_round_trips(store):
    await store.put_part_status("PART-A",
                                [{"distributor": "lcsc", "state": "ok"}], AS_OF)

    row = await store.get_part_status("PART-A")

    assert row.statuses[0]["distributor"] == "lcsc"
    assert await store.get_part_status("PART-B") is None


async def test_offers_by_sku_returns_only_the_pairs_asked_for(store):
    await store.put_offers([
        offer("PART-A", "lcsc", "C1"),
        offer("PART-B", "mouser", "M1"),
        offer("PART-C", "digikey", "D1"),
    ])

    got = await store.get_offers_by_sku([("lcsc", "C1"), ("digikey", "D1")])

    assert {(o.distributor, o.sku) for o in got} == {("lcsc", "C1"),
                                                     ("digikey", "D1")}


async def test_offers_by_sku_does_not_mix_distributors(store):
    """A SKU is only unique within its own distributor."""
    await store.put_offers([offer("PART-A", "lcsc", "SAME"),
                            offer("PART-B", "mouser", "SAME")])

    got = await store.get_offers_by_sku([("mouser", "SAME")])

    assert [(o.distributor, o.listing_key) for o in got] == [("mouser", "PART-B")]


async def test_empty_lookups_ask_the_database_nothing(store):
    assert await store.get_offers([]) == []
    assert await store.get_offers_by_sku([]) == []


async def test_find_part_key_by_sku_powers_the_legacy_redirect(store):
    await store.put_offers([offer("STM32F103C8T6", "lcsc", "C8734")])

    assert await store.find_part_key_by_sku("lcsc", "C8734") == "STM32F103C8T6"
    assert await store.find_part_key_by_sku("lcsc", "C9999") is None


async def test_parametric_rows_round_trip(store):
    rows = [{"lcsc": "C1", "resistance": 10000.0}, {"lcsc": "C2"}]
    await store.put_parametric("resistors|0603|", rows, AS_OF)

    got = await store.get_parametric("resistors|0603|")

    assert got == (rows, AS_OF)
    assert await store.get_parametric("capacitors|0402|") is None


async def test_quota_markers_round_trip(store):
    await store.put_quota_marker("mouser", AS_OF)

    assert await store.get_quota_markers() == {"mouser": AS_OF}


async def test_prune_drops_rows_too_old_to_serve(store):
    """Nothing evicts on its own, so on a host with a real volume the cache
    grows forever. A row past the freshness gates can never be returned."""
    old = AS_OF - timedelta(days=30)
    await store.put_offers([offer("OLD", "lcsc", "C1", as_of=old),
                            offer("NEW", "lcsc", "C2", as_of=AS_OF)])
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
    assert await store.prune(AS_OF - timedelta(days=7)) == 0


async def test_timestamps_come_back_as_the_utc_they_went_in_as(store):
    """Every freshness gate compares these, so a naive value would raise."""
    await store.put_offers([offer()])

    got = (await store.get_offers(["PART-A"]))[0]

    assert got.as_of.tzinfo is not None
    assert got.as_of == AS_OF
    assert (AS_OF - got.as_of) == timedelta(0)


@pytest.mark.live
async def test_postgres_rebuilds_the_cache_when_the_stamped_version_is_wrong():
    """Opening skips the rebuild when the version already matches, so this
    checks the other half: a stale stamp still gets the tables rebuilt."""
    dsn = os.environ.get("TEST_PG_DSN")
    if not dsn:
        pytest.skip("set TEST_PG_DSN to a throwaway database")
    store = PostgresCacheStore(dsn)
    await store.open()
    await store.put_offers([offer()])
    async with store._pool.acquire() as conn:
        await conn.execute("UPDATE cache_schema_meta SET version = $1",
                           CACHE_SCHEMA_VERSION - 1)
    await store.close()

    reopened = PostgresCacheStore(dsn)
    await reopened.open()
    try:
        assert await reopened.get_offers(["PART-A"]) == []
        async with reopened._pool.acquire() as conn:
            stamped = await conn.fetchval("SELECT version FROM cache_schema_meta")
        assert stamped == CACHE_SCHEMA_VERSION
    finally:
        await reopened.close()
