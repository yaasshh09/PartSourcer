from datetime import datetime, timezone

import pytest

from history.recorder import record_watchlist
from history.store import InMemoryHistoryStore
from models.part import PartDetail
from services.datasource import UpstreamError

pytestmark = pytest.mark.anyio

FIXED = datetime(2026, 8, 8, 3, 0, tzinfo=timezone.utc)


def detail(lcsc="C8734", mpn="STM32F103C8T6", price=1.82, stock=12400):
    return PartDetail(lcsc=lcsc, mpn=mpn, brand=None, package="LQFP-48",
                      description="", stock=stock, price_usd=price,
                      price_breaks=None, stock_breakdown=None,
                      is_basic=True, is_preferred=None, datasheet_url=None,
                      as_of=FIXED)


class FakeDs:
    """Duck-typed LcscMatcherSource: the recorder resolves a code, then
    re-reads the part on the basis the pages publish.

    `canonical` overrides what that second read returns; left unset it
    echoes the first, which is upstream agreeing with itself.
    """

    def __init__(self, parts=None, fail_on=(), canonical=None):
        self.parts = parts or {}
        self.fail_on = set(fail_on)
        self.canonical = canonical or {}
        self.calls = []
        self.allow_cached = []

    async def get_part(self, lcsc_code, refresh=False):
        self.calls.append(lcsc_code)
        if lcsc_code in self.fail_on:
            raise UpstreamError("unavailable", "boom")
        return self.parts.get(lcsc_code)

    async def canonical_part(self, mpn, lcsc_code, allow_cached=True):
        self.allow_cached.append(allow_cached)
        if mpn in self.canonical:
            return self.canonical[mpn]
        if lcsc_code in self.canonical:
            return self.canonical[lcsc_code]
        return self.parts.get(lcsc_code)

    async def list_parametric(self, category, package, resistance_ohms=None):
        return []


async def test_empty_watchlist_records_nothing():
    store = InMemoryHistoryStore()
    summary = await record_watchlist(FakeDs(), store, batch_size=10,
                                     concurrency=2, now=lambda: FIXED)
    assert (summary.recorded, summary.errors) == (0, 0)


async def test_records_one_row_per_watchlist_part():
    store = InMemoryHistoryStore()
    await store.add_to_watchlist("STM32F103C8T6", "C8734")
    ds = FakeDs({"C8734": detail()})
    summary = await record_watchlist(ds, store, batch_size=10, concurrency=2,
                                     now=lambda: FIXED)
    assert summary.recorded == 1
    r = store.records[0]
    assert (r.mpn_key, r.distributor, r.price_usd, r.stock) == (
        "STM32F103C8T6", "lcsc", 1.82, 12400)
    assert r.recorded_at == FIXED


async def test_a_part_with_no_price_is_skipped_not_recorded_as_free():
    # History is append-only, so a 0.0 written once is a permanent false
    # low in the price chart for that part.
    store = InMemoryHistoryStore()
    await store.add_to_watchlist("STM32F103C8T6", "C8734")
    ds = FakeDs({"C8734": detail(price=None)})
    summary = await record_watchlist(ds, store, batch_size=10, concurrency=2,
                                     now=lambda: FIXED)
    assert (summary.recorded, summary.skipped, summary.errors) == (0, 1, 0)
    assert store.records == []


async def test_upstream_failure_counts_as_error_and_does_not_abort():
    store = InMemoryHistoryStore()
    await store.add_to_watchlist("BAD", "C1")
    await store.add_to_watchlist("STM32F103C8T6", "C8734")
    ds = FakeDs({"C8734": detail()}, fail_on=["C1"])
    summary = await record_watchlist(ds, store, batch_size=10, concurrency=2,
                                     now=lambda: FIXED)
    assert (summary.recorded, summary.errors) == (1, 1)


async def test_missing_part_counts_as_skipped():
    store = InMemoryHistoryStore()
    await store.add_to_watchlist("GONE", "C999")
    ds = FakeDs({})
    summary = await record_watchlist(ds, store, batch_size=10, concurrency=2,
                                     now=lambda: FIXED)
    assert (summary.recorded, summary.skipped) == (0, 1)


async def test_batch_size_caps_the_watchlist_read():
    store = InMemoryHistoryStore()
    for i in range(5):
        await store.add_to_watchlist(f"MPN{i}", f"C{i}")
    ds = FakeDs({f"C{i}": detail(lcsc=f"C{i}", mpn=f"MPN{i}") for i in range(5)})
    summary = await record_watchlist(ds, store, batch_size=2, concurrency=2,
                                     now=lambda: FIXED)
    assert summary.recorded == 2


async def test_entry_without_lcsc_is_skipped():
    store = InMemoryHistoryStore()
    await store.add_to_watchlist("NOLCSC", None)
    summary = await record_watchlist(FakeDs(), store, batch_size=10,
                                     concurrency=2, now=lambda: FIXED)
    assert (summary.recorded, summary.skipped) == (0, 1)


async def test_the_recorded_price_is_the_one_the_pages_show():
    """Upstream answers differently depending on how a part is asked for.
    History is append-only, so a row written on the resolving read's basis
    would sit permanently below the price the part's own page quotes."""
    store = InMemoryHistoryStore()
    await store.add_to_watchlist("STM32F103C8T6", "C8734")
    ds = FakeDs(parts={"C8734": detail(price=0.0039, stock=8013731)},
                canonical={"C8734": detail(price=0.0009, stock=15873089)})

    await record_watchlist(ds, store, batch_size=10, concurrency=2,
                           now=lambda: FIXED)

    assert [r.price_usd for r in store.records] == [0.0009]
    assert [r.stock for r in store.records] == [15873089]


async def test_a_part_missing_from_the_published_read_is_skipped():
    store = InMemoryHistoryStore()
    await store.add_to_watchlist("STM32F103C8T6", "C8734")
    ds = FakeDs(parts={"C8734": detail(price=0.0039)},
                canonical={"C8734": None})

    summary = await record_watchlist(ds, store, batch_size=10, concurrency=2,
                                     now=lambda: FIXED)

    assert (summary.recorded, summary.skipped) == (0, 1)
    assert store.records == []


async def test_the_recorder_reads_now_rather_than_from_cache():
    """A point is stamped with the run's time, so it has to be read at that
    time. A cached row could be most of a TTL old and would date the chart."""
    store = InMemoryHistoryStore()
    await store.add_to_watchlist("STM32F103C8T6", "C8734")
    ds = FakeDs(parts={"C8734": detail()})

    await record_watchlist(ds, store, batch_size=10, concurrency=2,
                           now=lambda: FIXED)

    assert ds.allow_cached == [False]


async def test_the_usual_entry_costs_one_upstream_read_not_two():
    """The watchlist already carries both keys, so resolving the code again
    was a wasted call against a free community upstream, every night, for
    every part."""
    store = InMemoryHistoryStore()
    await store.add_to_watchlist("STM32F103C8T6", "C8734")
    ds = FakeDs(parts={"C8734": detail()})

    await record_watchlist(ds, store, batch_size=10, concurrency=2,
                           now=lambda: FIXED)

    assert ds.calls == [], "resolved the code when it did not need to"
    assert len(store.records) == 1


async def test_a_key_that_does_not_resolve_falls_back_to_the_code():
    store = InMemoryHistoryStore()
    await store.add_to_watchlist("RENAMED", "C8734")
    ds = FakeDs(parts={"C8734": detail()}, canonical={"RENAMED": None})

    await record_watchlist(ds, store, batch_size=10, concurrency=2,
                           now=lambda: FIXED)

    assert ds.calls == ["C8734"], "did not fall back"
    assert len(store.records) == 1
