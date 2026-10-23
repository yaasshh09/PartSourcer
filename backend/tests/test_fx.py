"""GET /api/fx and the rate cache behind it."""

import httpx
import pytest
from fastapi.testclient import TestClient

import services.deps as deps
from main import app
from services.fx import FxRates

GOOD = {"amount": 1.0, "base": "USD", "date": "2026-10-23",
        "rates": {"EUR": 0.89342, "GBP": 0.74804, "INR": 94.94}}


def rates_over(handler, now=lambda: 0.0):
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return FxRates(client, "https://fx.test", now=now)


def teardown_function():
    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_reads_usd_based_rates_and_asks_only_for_what_is_shown():
    seen = []

    def handler(request):
        seen.append(request.url)
        return httpx.Response(200, json=GOOD)
    body = await rates_over(handler).get()
    assert body == {"base": "USD", "date": "2026-10-23",
                    "rates": {"EUR": 0.89342, "GBP": 0.74804, "INR": 94.94}}
    assert seen[0].params["base"] == "USD" and seen[0].params["symbols"] == "EUR,GBP,INR"


@pytest.mark.anyio
async def test_one_upstream_read_per_ttl():
    calls, clock = [], [0.0]

    def handler(request):
        calls.append(1)
        return httpx.Response(200, json=GOOD)
    fx = rates_over(handler, now=lambda: clock[0])
    await fx.get()
    clock[0] = 60
    await fx.get()
    assert len(calls) == 1
    clock[0] = 7 * 3600
    await fx.get()
    assert len(calls) == 2


@pytest.mark.anyio
async def test_an_upstream_failure_keeps_the_last_dated_rates_or_raises():
    clock, ok = [0.0], [True]

    def handler(request):
        return httpx.Response(200, json=GOOD) if ok[0] else httpx.Response(500)
    fx = rates_over(handler, now=lambda: clock[0])
    await fx.get()
    ok[0], clock[0] = False, 7 * 3600
    assert (await fx.get())["date"] == "2026-10-23"

    cold = rates_over(lambda r: httpx.Response(500))
    with pytest.raises(Exception):
        await cold.get()


@pytest.mark.anyio
async def test_a_missing_or_silly_rate_is_dropped_not_guessed():
    bad = {**GOOD, "rates": {"EUR": 0.9, "GBP": 0, "INR": "x"}}
    body = await rates_over(lambda r: httpx.Response(200, json=bad)).get()
    assert body["rates"] == {"EUR": 0.9}


def test_route_returns_rates_with_a_cache_header():
    class Stub:
        async def get(self):
            return {"base": "USD", "date": "2026-10-23", "rates": {"EUR": 0.9}}
    app.dependency_overrides[deps.get_fx] = lambda: Stub()
    resp = TestClient(app).get("/api/fx")
    assert resp.status_code == 200
    assert resp.json()["rates"] == {"EUR": 0.9}
    assert "max-age" in resp.headers["cache-control"]


def test_route_is_a_503_when_no_rate_was_ever_read():
    class Down:
        async def get(self):
            raise RuntimeError("down")
    app.dependency_overrides[deps.get_fx] = lambda: Down()
    assert TestClient(app).get("/api/fx").status_code == 503
