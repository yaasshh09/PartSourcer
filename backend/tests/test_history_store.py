from datetime import datetime, timezone

import pytest

from history.store import InMemoryHistoryStore, OfferRecord

pytestmark = pytest.mark.anyio


def rec(mpn_key="STM32F103C8T6", price=1.82, stock=12400):
    return OfferRecord(
        mpn_key=mpn_key, lcsc="C8734", distributor="lcsc", sku="C8734",
        price_usd=price, stock=stock, in_stock=stock > 0, currency="USD",
        recorded_at=datetime(2026, 8, 8, 3, 0, tzinfo=timezone.utc))


@pytest.fixture
def store():
    return InMemoryHistoryStore()


async def test_watchlist_starts_empty(store):
    assert await store.get_watchlist(limit=10) == []


async def test_add_to_watchlist_then_read(store):
    await store.add_to_watchlist("STM32F103C8T6", "C8734")
    assert await store.get_watchlist(limit=10) == [("STM32F103C8T6", "C8734")]


async def test_watchlist_deduplicates(store):
    await store.add_to_watchlist("STM32F103C8T6", "C8734")
    await store.add_to_watchlist("STM32F103C8T6", "C8734")
    assert len(await store.get_watchlist(limit=10)) == 1


async def test_watchlist_respects_limit(store):
    for i in range(5):
        await store.add_to_watchlist(f"MPN{i}", None)
    assert len(await store.get_watchlist(limit=3)) == 3


async def test_record_offers_returns_count_and_appends(store):
    assert await store.record_offers([rec(), rec(price=1.75)]) == 2
    assert len(store.records) == 2


async def test_record_offers_never_overwrites(store):
    await store.record_offers([rec(price=1.82)])
    await store.record_offers([rec(price=1.75)])
    assert [r.price_usd for r in store.records] == [1.82, 1.75]
