"""GET /api/history/{mpn_key}: the recorded LCSC price and stock for a part.

The page draws a chart from it, so it has to say plainly when nothing is
being recorded rather than hand back an empty list that reads as "no data
yet".
"""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

import services.deps as deps
from history.store import InMemoryHistoryStore, OfferRecord
from main import app


def teardown_function():
    app.dependency_overrides.clear()


def row(days_ago, price, stock=100, key="STM32F103C8T6"):
    return OfferRecord(
        mpn_key=key, lcsc="C8734", distributor="lcsc", sku="C8734",
        price_usd=price, stock=stock, in_stock=stock > 0, currency="USD",
        recorded_at=datetime.now(timezone.utc) - timedelta(days=days_ago))


def get(store, path="/api/history/stm32f103c8t6"):
    app.dependency_overrides[deps.get_history_store] = lambda: store
    return TestClient(app).get(path)


def test_points_come_back_oldest_first_under_the_normalized_key():
    store = InMemoryHistoryStore()
    store.records = [row(1, 1.75, 900), row(3, 1.82, 1200), row(1, 9.0, key="OTHER")]
    resp = get(store)
    assert resp.status_code == 200
    body = resp.json()
    assert body["recording"] is True and body["distributor"] == "lcsc"
    assert [p["price_usd"] for p in body["points"]] == [1.82, 1.75]
    assert [p["stock"] for p in body["points"]] == [1200, 900]
    assert "max-age=3600" in resp.headers["cache-control"]


def test_the_window_drops_older_rows():
    store = InMemoryHistoryStore()
    store.records = [row(200, 3.0), row(10, 2.0)]
    assert [p["price_usd"] for p in get(store, "/api/history/STM32F103C8T6?days=30").json()["points"]] == [2.0]
    assert get(store, "/api/history/STM32F103C8T6?days=0").status_code == 422
    assert get(store, "/api/history/STM32F103C8T6?days=9999").status_code == 422


def test_no_store_says_it_is_not_recording():
    body = get(None).json()
    assert body["recording"] is False and body["points"] == []


def test_a_store_that_fails_is_an_error_not_an_empty_chart():
    class Broken(InMemoryHistoryStore):
        async def get_history(self, mpn_key, since):
            raise OSError("db down")
    assert get(Broken()).status_code == 503
