"""GET /api/suggest: part numbers people have opened, for the search box."""

from fastapi.testclient import TestClient

import services.deps as deps
from history.store import InMemoryHistoryStore
from main import app


def teardown_function():
    app.dependency_overrides.clear()


def get(store, q):
    app.dependency_overrides[deps.get_history_store] = lambda: store
    return TestClient(app).get("/api/suggest", params={"q": q})


def store_with(*keys):
    store = InMemoryHistoryStore()
    for k in keys:
        store.watchlist[k] = None
    return store


def test_prefix_matches_come_back_newest_first_whatever_the_case():
    resp = get(store_with("STM32F103C8T6", "NE555DR", "STM32F030F4P6"), " stm32 ")
    assert resp.status_code == 200
    assert resp.json() == {"suggestions": ["STM32F030F4P6", "STM32F103C8T6"]}
    assert "max-age" in resp.headers["cache-control"]


def test_a_like_wildcard_is_just_a_character():
    assert get(store_with("A_B", "AXB"), "a_").json() == {"suggestions": ["A_B"]}


def test_one_character_or_no_store_suggests_nothing():
    assert get(store_with("NE555DR"), "n").json() == {"suggestions": []}
    assert get(None, "ne5").json() == {"suggestions": []}


def test_at_most_eight():
    keys = [f"R{i:02d}" for i in range(20)]
    assert len(get(store_with(*keys), "r").json()["suggestions"]) == 0
    assert len(get(store_with(*keys), "r0").json()["suggestions"]) == 8


def test_a_store_that_fails_suggests_nothing_rather_than_erroring():
    class Broken(InMemoryHistoryStore):
        async def suggest(self, prefix, limit):
            raise RuntimeError("db down")
    assert get(Broken(), "ne5").json() == {"suggestions": []}
