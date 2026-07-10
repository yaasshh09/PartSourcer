import httpx
import pytest
from fastapi.testclient import TestClient

import services.deps as deps
from main import app
from cache.caching_datasource import CachingPartDataSource
from cache.store import SqliteCacheStore
from config import settings
from services.datasource import JlcSearchDataSource

RAW = {"lcsc": 8734, "mfr": "STM32F103C8T6", "package": "LQFP-48(7x7)",
       "is_basic": False, "is_preferred": True, "description": "",
       "stock": 214596, "price": 1.037142857}


def client_with(handler):
    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(base_url="https://example.test",
                                    transport=transport)
    ds = JlcSearchDataSource(http_client)
    app.dependency_overrides[deps.get_datasource] = lambda: ds
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


def test_detail_shape():
    c = client_with(lambda req: httpx.Response(200, json={"components": [RAW]}))
    resp = c.get("/api/part/C8734")
    assert resp.status_code == 200
    b = resp.json()
    assert b["lcsc"] == "C8734"
    assert b["mpn"] == "STM32F103C8T6"
    assert b["is_basic"] is False and b["is_preferred"] is True
    assert b["price_breaks"] is None and b["stock_breakdown"] is None
    assert b["price_usd"] == 1.0371
    assert b["brand"] is None and b["datasheet_url"] is None


def test_not_found_returns_404():
    c = client_with(lambda req: httpx.Response(200, json={"components": []}))
    resp = c.get("/api/part/C000000")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Part C000000 not found"


def test_malformed_code_returns_404():
    # A non-numeric code is rejected in the datasource before any upstream
    # call — this handler must never run, so it fails loudly if it does.
    def handler(request):
        raise AssertionError("upstream must not be called for a malformed code")

    c = client_with(handler)
    resp = c.get("/api/part/not-a-code")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Part not-a-code not found"


def test_timeout_maps_to_504():
    def handler(request):
        raise httpx.ConnectTimeout("boom")

    c = client_with(handler)
    assert c.get("/api/part/C8734").status_code == 504


def test_upstream_error_maps_to_502():
    c = client_with(lambda req: httpx.Response(500, text="oops"))
    assert c.get("/api/part/C8734").status_code == 502


@pytest.fixture
def cache_client(tmp_path):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(200, json={"components": [RAW]})

    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(base_url="https://example.test",
                                    transport=transport)
    store = SqliteCacheStore(str(tmp_path / "cache.db"))
    store.open()
    ds = CachingPartDataSource(inner=JlcSearchDataSource(http_client),
                               store=store,
                               specs_ttl_secs=settings.specs_cache_ttl_secs,
                               stock_ttl_secs=settings.stock_cache_ttl_secs)
    app.dependency_overrides[deps.get_datasource] = lambda: ds
    yield TestClient(app), calls
    store.close()


def test_second_detail_served_from_cache(cache_client):
    c, calls = cache_client
    first = c.get("/api/part/C8734").json()
    second = c.get("/api/part/C8734").json()
    assert calls["n"] == 1
    assert second == first


def test_refresh_forces_refetch(cache_client):
    c, calls = cache_client
    c.get("/api/part/C8734")
    c.get("/api/part/C8734", params={"refresh": "true"})
    assert calls["n"] == 2
