"""Live Postgres tests. Deselected by default.

Run with:  pytest -m live --dsn from DATABASE_URL in backend/.env
"""
import os
from datetime import datetime, timezone

import pytest

from history.store import OfferRecord, PostgresHistoryStore

pytestmark = [pytest.mark.anyio, pytest.mark.live]


@pytest.fixture
async def pg():
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        pytest.skip("DATABASE_URL not set")
    store = PostgresHistoryStore(dsn)
    await store.open()
    yield store
    await store.close()


async def test_watchlist_round_trip(pg):
    await pg.add_to_watchlist("TESTMPN001", "C1")
    entries = dict(await pg.get_watchlist(limit=1000))
    assert entries.get("TESTMPN001") == "C1"


async def test_record_offers_appends(pg):
    r = OfferRecord(mpn_key="TESTMPN001", lcsc="C1", distributor="lcsc",
                    sku="C1", price_usd=1.0, stock=10, in_stock=True,
                    currency="USD", recorded_at=datetime.now(timezone.utc))
    assert await pg.record_offers([r]) == 1
