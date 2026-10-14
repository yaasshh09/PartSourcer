"""GET /api/trends: week-on-week LCSC price and stock change for search cards.

One request covers a whole results page, so a search costs one extra call,
not one per card.
"""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

import services.deps as deps
from history.store import InMemoryHistoryStore, OfferRecord
from main import app


def teardown_function():
    app.dependency_overrides.clear()


def row(key, days_ago, price, stock):
    return OfferRecord(
        mpn_key=key, lcsc="C1", distributor="lcsc", sku="C1",
        price_usd=price, stock=stock, in_stock=stock > 0, currency="USD",
        recorded_at=datetime.now(timezone.utc) - timedelta(days=days_ago, hours=1))


def get(store, qs):
    app.dependency_overrides[deps.get_history_store] = lambda: store
    return TestClient(app).get(f"/api/trends?{qs}")


def test_change_runs_from_the_oldest_to_the_newest_reading_in_the_week():
    store = InMemoryHistoryStore()
    store.records = [row("A", 6, 1.00, 1000), row("A", 3, 0.95, 800), row("A", 0, 0.80, 400),
                     row("A", 30, 5.0, 9), row("B", 5, 2.0, 0), row("B", 1, 2.0, 50)]
    resp = get(store, "keys=a&keys=B&keys=C")
    assert resp.status_code == 200
    t = resp.json()["trends"]
    assert t["A"]["price_pct"] == -20 and t["A"]["stock_pct"] == -60
    # Nothing to divide by: a part coming back from zero stock has no percent.
    assert t["B"]["price_pct"] == 0 and t["B"]["stock_pct"] is None
    assert "C" not in t
    assert "max-age=3600" in resp.headers["cache-control"]


def test_readings_too_close_together_are_not_a_trend():
    store = InMemoryHistoryStore()
    store.records = [row("A", 0, 1.0, 10), row("A", 0, 0.5, 10)]
    assert get(store, "keys=A").json()["trends"] == {}


def test_bounds_and_no_store():
    assert get(InMemoryHistoryStore(), "").status_code == 422
    assert get(InMemoryHistoryStore(), "&".join(f"keys=K{i}" for i in range(51))).status_code == 422
    body = get(None, "keys=A").json()
    assert body["recording"] is False and body["trends"] == {}
