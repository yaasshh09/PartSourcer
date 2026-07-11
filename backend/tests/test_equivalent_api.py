import httpx
import pytest
from fastapi.testclient import TestClient

import services.deps as deps
from main import app
from services.datasource import JlcSearchDataSource

# Upstream rows. A resistor lookup drives: search-by-code (get_part) via
# /api/search, then /resistors/list.json (classify + pool).
RES_ROW = {"lcsc": 100, "mfr": "R-orig", "package": "0603", "is_basic": True,
           "is_preferred": False, "description": "", "stock": 1000,
           "price": 0.0010, "price1": 0.0010, "in_stock": True,
           "resistance": 10000, "tolerance_fraction": 0.01, "power_watts": 100}
RES_CHEAP = {"lcsc": 1, "mfr": "R-cheap", "package": "0603", "is_basic": False,
             "is_preferred": False, "description": "", "stock": 900000,
             "price": 0.0004, "price1": 0.0004, "in_stock": True,
             "resistance": 10000, "tolerance_fraction": 0.01, "power_watts": 100}
IC_ROW = {"lcsc": 8734, "mfr": "STM32F103C8T6", "package": "LQFP-48(7x7)",
          "is_basic": False, "is_preferred": True, "description": "",
          "stock": 214596, "price": 1.0371}


def route(request):
    p = request.url.path
    if p == "/api/search":
        q = request.url.params.get("q", "")
        if "8734" in q:
            return httpx.Response(200, json={"components": [IC_ROW]})
        return httpx.Response(200, json={"components": [RES_ROW]})
    if p == "/resistors/list.json":
        return httpx.Response(200, json={"resistors": [RES_ROW, RES_CHEAP]})
    if p == "/capacitors/list.json":
        return httpx.Response(200, json={"capacitors": []})
    return httpx.Response(404, json={})


def client_with(handler):
    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(base_url="https://example.test",
                                    transport=transport)
    ds = JlcSearchDataSource(http_client)
    app.dependency_overrides[deps.get_datasource] = lambda: ds
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


def test_equivalent_found_for_resistor():
    c = client_with(route)
    resp = c.get("/api/part/C100/equivalent")
    assert resp.status_code == 200
    b = resp.json()
    assert b["original"]["lcsc"] == "C100"
    assert b["equivalent"]["lcsc"] == "C1"
    assert b["equivalent"]["percent_cheaper"] == 60
    assert b["reason"] is None


def test_equivalent_null_for_ic():
    c = client_with(route)
    resp = c.get("/api/part/C8734/equivalent")
    assert resp.status_code == 200
    b = resp.json()
    assert b["equivalent"] is None
    assert "resistors and capacitors" in b["reason"]


def test_equivalent_unknown_code_404():
    c = client_with(lambda req: httpx.Response(200, json={"components": []}))
    assert c.get("/api/part/C999999/equivalent").status_code == 404


def test_equivalent_timeout_504():
    def handler(request):
        raise httpx.ConnectTimeout("boom")
    c = client_with(handler)
    assert c.get("/api/part/C100/equivalent").status_code == 504


def test_equivalent_upstream_error_502():
    c = client_with(lambda req: httpx.Response(500, text="oops"))
    assert c.get("/api/part/C100/equivalent").status_code == 502
