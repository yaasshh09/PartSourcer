"""GET /api/status: how each distributor answered over the past day."""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

import services.deps as deps
from main import app

NOW = datetime.now(timezone.utc)


def teardown_function():
    app.dependency_overrides.clear()


class Store:
    def __init__(self, rows, fail=False):
        self.rows, self.fail, self.asked = rows, fail, None

    async def recent_statuses(self, since, limit):
        self.asked = (since, limit)
        if self.fail:
            raise RuntimeError("db down")
        return self.rows


def get(store):
    app.dependency_overrides[deps.get_cache_store] = lambda: store
    return TestClient(app).get("/api/status")


def s(dist, state):
    return {"distributor": dist, "state": state, "detail": None, "as_of": None}


def test_counts_each_distributors_answers_and_dates_the_last_good_and_bad():
    rows = [
        (NOW - timedelta(minutes=5), [s("lcsc", "ok"), s("mouser", "timeout"), s("digikey", "disabled")]),
        (NOW - timedelta(hours=2), [s("lcsc", "unavailable"), s("mouser", "ok"), s("digikey", "disabled")]),
        (NOW - timedelta(hours=3), [s("lcsc", "ok"), s("mouser", "ok"), s("digikey", "disabled")]),
    ]
    store = Store(rows)
    resp = get(store)
    assert resp.status_code == 200
    body = resp.json()
    assert body["window_hours"] == 24 and body["reads"] == 3
    by = {d["distributor"]: d for d in body["distributors"]}
    assert [d["distributor"] for d in body["distributors"]] == ["lcsc", "mouser", "digikey"]
    assert by["lcsc"]["ok"] == 2 and by["lcsc"]["problems"] == {"unavailable": 1}
    assert by["lcsc"]["last_problem"]["state"] == "unavailable"
    assert by["mouser"]["last_ok_at"].startswith((NOW - timedelta(hours=2)).isoformat()[:13])
    assert by["digikey"]["configured"] is False and by["digikey"]["ok"] == 0
    assert store.asked[1] == 2000
    assert NOW - store.asked[0] > timedelta(hours=23)
    assert "max-age" in resp.headers["cache-control"]


def test_a_quiet_day_is_zero_reads_not_an_error():
    body = get(Store([])).json()
    assert body["reads"] == 0
    assert all(d["ok"] == 0 and d["configured"] is None for d in body["distributors"])


def test_an_unreadable_cache_is_a_503():
    assert get(Store([], fail=True)).status_code == 503
