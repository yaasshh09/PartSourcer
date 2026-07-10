import httpx
from fastapi.testclient import TestClient

import services.deps as deps
from main import app
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


def test_search_shape_matches_section9():
    c = client_with(lambda req: httpx.Response(200, json={"components": [RAW]}))
    resp = c.get("/api/search", params={"q": "STM32F103"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["page"] == 1
    r = body["results"][0]
    assert r["lcsc"] == "C8734"
    assert r["mpn"] == "STM32F103C8T6"
    assert r["brand"] is None and r["datasheet_url"] is None
    assert r["price_usd"] == 1.0371
    assert "as_of" in r


def test_empty_query_returns_empty_results():
    c = client_with(lambda req: httpx.Response(200, json={"components": [RAW]}))
    resp = c.get("/api/search", params={"q": ""})
    assert resp.status_code == 200
    assert resp.json() == {"page": 1, "results": []}


def test_page_must_be_positive():
    c = client_with(lambda req: httpx.Response(200, json={"components": []}))
    assert c.get("/api/search", params={"q": "x", "page": 0}).status_code == 422


def test_timeout_maps_to_504():
    def handler(request):
        raise httpx.ConnectTimeout("boom")

    c = client_with(handler)
    assert c.get("/api/search", params={"q": "x"}).status_code == 504


def test_upstream_error_maps_to_502():
    c = client_with(lambda req: httpx.Response(500, text="oops"))
    assert c.get("/api/search", params={"q": "x"}).status_code == 502


# --- caching integration (Prompt 4) ---

from cache.caching_datasource import CachingPartDataSource
from cache.store import SqliteCacheStore
from config import settings


import pytest


@pytest.fixture
def cache_client(tmp_path):
    """TestClient wired through the real cache over a mock transport."""
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
    store.close()  # release the file so Windows tmp_path cleanup succeeds


def test_second_identical_search_served_from_cache(cache_client):
    c, calls = cache_client
    first = c.get("/api/search", params={"q": "STM32F103"}).json()
    second = c.get("/api/search", params={"q": "STM32F103"}).json()
    assert calls["n"] == 1                                   # one upstream hit
    assert second == first                                   # same as_of too


def test_refresh_param_forces_upstream_refetch(cache_client):
    c, calls = cache_client
    c.get("/api/search", params={"q": "STM32F103"})
    c.get("/api/search", params={"q": "STM32F103", "refresh": "true"})
    assert calls["n"] == 2
