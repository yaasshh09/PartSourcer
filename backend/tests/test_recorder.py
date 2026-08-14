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
    """Duck-typed LcscMatcherSource: the recorder only ever calls get_part."""

    def __init__(self, parts=None, fail_on=()):
        self.parts = parts or {}
        self.fail_on = set(fail_on)
        self.calls = []

    async def get_part(self, lcsc_code, refresh=False):
        self.calls.append(lcsc_code)
        if lcsc_code in self.fail_on:
            raise UpstreamError("unavailable", "boom")
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
