"""Error shapes on the search route: one {"detail": str} for everything."""

from fastapi.testclient import TestClient

import services.deps as deps
from main import app
from services.datasource import UpstreamError
from tests.stub_cached import StubCached


def teardown_function():
    app.dependency_overrides.clear()


def _client(stub, raise_server_exceptions=True):
    app.dependency_overrides[deps.get_cached_service] = lambda: stub
    return TestClient(app, raise_server_exceptions=raise_server_exceptions)


def test_validation_error_is_detail_shape():
    c = _client(StubCached())
    resp = c.get("/api/search", params={"q": "x", "page": 0})  # page ge=1
    assert resp.status_code == 422
    body = resp.json()
    assert set(body.keys()) == {"detail"}
    assert isinstance(body["detail"], str) and body["detail"]


def test_upstream_timeout_is_detail_shape_504():
    c = _client(StubCached(error=UpstreamError("timeout", "upstream timed out")))
    resp = c.get("/api/search", params={"q": "x"})
    assert resp.status_code == 504
    assert isinstance(resp.json()["detail"], str)


def test_upstream_unavailable_is_detail_shape_502():
    c = _client(StubCached(error=UpstreamError("unavailable", "upstream down")))
    resp = c.get("/api/search", params={"q": "x"})
    assert resp.status_code == 502
    assert isinstance(resp.json()["detail"], str)


def test_unexpected_exception_is_500_detail():
    c = _client(StubCached(error=RuntimeError("unexpected")),
                raise_server_exceptions=False)
    resp = c.get("/api/search", params={"q": "x"})
    assert resp.status_code == 500
    assert resp.json() == {"detail": "internal server error"}


def test_cors_allows_dev_origin_on_get():
    c = _client(StubCached())
    resp = c.get("/api/search", params={"q": "x"},
                 headers={"Origin": "http://localhost:5173"})
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_preflight_ok():
    c = _client(StubCached())
    resp = c.options("/api/search",
                     headers={"Origin": "http://localhost:5173",
                              "Access-Control-Request-Method": "GET"})
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "http://localhost:5173"
