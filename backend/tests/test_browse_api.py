"""GET /api/browse and /api/browse/{slug} over a mocked upstream."""

import httpx
from fastapi.testclient import TestClient

import services.deps as deps
from main import app
from services.adapters.lcsc import LcscAdapter
from services.browse import BrowseService
from services.datasource import UPSTREAM_STATUS

RES = {"lcsc": 25804, "mfr": "0603WAF1002T5E", "package": "0603",
       "stock": 37165617, "price1": 0.000842857, "resistance": 10000,
       "tolerance_fraction": 0.01, "power_watts": 100}


def client_for(status=200, rows=(RES,)):
    def handler(request):
        if status != 200:
            return httpx.Response(status, json={})
        return httpx.Response(200, json={request.url.path.split("/")[1]: list(rows)})
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler),
                             base_url="https://jlcsearch.test")
    svc = BrowseService(LcscAdapter(http))
    app.dependency_overrides[deps.get_browse_service] = lambda: svc
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


def test_categories_are_listed_with_their_filters():
    body = client_for().get("/api/browse").json()
    assert [c["slug"] for c in body["categories"]][:2] == ["resistors", "capacitors"]
    res = body["categories"][0]
    assert {f["name"] for f in res["filters"]} == {"package", "resistance", "basic"}


def test_browse_returns_rows_without_any_price():
    resp = client_for().get("/api/browse/resistors?package=0603")
    assert resp.status_code == 200
    body = resp.json()
    assert body["results"][0]["lcsc"] == "C25804"
    assert body["count"] == 1 and body["capped"] is False and body["as_of"]
    assert "price" not in resp.text


def test_unknown_category_is_404():
    resp = client_for().get("/api/browse/rockets")
    assert resp.status_code == 404
    assert "rockets" in resp.json()["detail"]


def test_a_bad_value_is_422_with_a_hint():
    resp = client_for().get("/api/browse/resistors?resistance=ten")
    assert resp.status_code == 422
    assert "10k" in resp.json()["detail"]


def test_an_unknown_filter_is_422():
    resp = client_for().get("/api/browse/resistors?refresh=true")
    assert resp.status_code == 422


def test_a_huge_value_is_a_short_422_not_a_500():
    resp = client_for().get("/api/browse/resistors?package=" + "x" * 5000)
    assert resp.status_code == 422
    assert len(resp.json()["detail"]) < 200


def test_upstream_failure_maps_like_search():
    resp = client_for(status=500).get("/api/browse/resistors")
    assert resp.status_code == UPSTREAM_STATUS["unavailable"]
