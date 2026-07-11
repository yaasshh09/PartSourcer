import httpx
from fastapi.testclient import TestClient

import services.deps as deps
from main import app
from services.datasource import JlcSearchDataSource, PartDataSource, UpstreamError


def teardown_function():
    app.dependency_overrides.clear()


def _client(handler):
    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(base_url="https://example.test", transport=transport)
    app.dependency_overrides[deps.get_datasource] = lambda: JlcSearchDataSource(http_client)
    return TestClient(app)


def test_validation_error_is_detail_shape():
    c = _client(lambda req: httpx.Response(200, json={"components": []}))
    resp = c.get("/api/search", params={"q": "x", "page": 0})  # page ge=1
    assert resp.status_code == 422
    body = resp.json()
    assert set(body.keys()) == {"detail"}
    assert isinstance(body["detail"], str) and body["detail"]


def test_upstream_timeout_is_detail_shape_504():
    def handler(req):
        raise httpx.ConnectTimeout("boom")
    c = _client(handler)
    resp = c.get("/api/search", params={"q": "x"})
    assert resp.status_code == 504
    assert isinstance(resp.json()["detail"], str)


def test_upstream_unavailable_is_detail_shape_502():
    c = _client(lambda req: httpx.Response(500, text="oops"))
    resp = c.get("/api/search", params={"q": "x"})
    assert resp.status_code == 502
    assert isinstance(resp.json()["detail"], str)


def test_unexpected_exception_is_500_detail():
    class Boom(PartDataSource):
        async def search(self, q, page, refresh=False):
            raise RuntimeError("unexpected")
        async def get_part(self, code, refresh=False):
            raise RuntimeError("unexpected")
        async def list_parametric(self, category, package, resistance_ohms=None):
            raise RuntimeError("unexpected")

    app.dependency_overrides[deps.get_datasource] = lambda: Boom()
    c = TestClient(app, raise_server_exceptions=False)
    resp = c.get("/api/search", params={"q": "x"})
    assert resp.status_code == 500
    assert resp.json() == {"detail": "internal server error"}


def test_cors_allows_dev_origin_on_get():
    c = _client(lambda req: httpx.Response(200, json={"components": []}))
    resp = c.get("/api/search", params={"q": "x"},
                 headers={"Origin": "http://localhost:5173"})
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_preflight_ok():
    c = _client(lambda req: httpx.Response(200, json={"components": []}))
    resp = c.options("/api/search",
                     headers={"Origin": "http://localhost:5173",
                              "Access-Control-Request-Method": "GET"})
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "http://localhost:5173"
