"""GET /api/equivalent/{mpn_key}.

The matcher itself is v1 logic and is not under test here beyond the fact
that it still runs end to end. What is new is how it is reached: by canonical
MPN, through the part's LCSC offer.
"""

import httpx
from fastapi.testclient import TestClient

import services.deps as deps
from main import app
from services.adapters.lcsc import LcscAdapter
from services.lcsc_matcher_source import LcscMatcherSource
from tests.stub_cached import StubCached, offer, part

# Upstream rows. A resistor lookup drives: lookup_sku via /api/search, then
# /resistors/list.json (classify + pool).
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

CAP_ROW = {"lcsc": 200, "mfr": "C-orig", "package": "0402", "is_basic": True,
           "is_preferred": False, "description": "", "stock": 1000,
           "price": 0.0030, "price1": 0.0030, "in_stock": True,
           "capacitance_farads": 1e-07, "voltage_rating": 16,
           "tolerance_fraction": 0.1, "temperature_coefficient": "X7R"}
CAP_CHEAP = {"lcsc": 2, "mfr": "C-cheap", "package": "0402", "is_basic": False,
             "is_preferred": False, "description": "", "stock": 500000,
             "price": 0.0012, "price1": 0.0012, "in_stock": True,
             "capacitance_farads": 1e-07, "voltage_rating": 25,
             "tolerance_fraction": 0.1, "temperature_coefficient": "C0G"}


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


def cap_route(request):
    p = request.url.path
    if p == "/api/search":
        return httpx.Response(200, json={"components": [CAP_ROW]})
    if p == "/capacitors/list.json":
        return httpx.Response(200, json={"capacitors": [CAP_ROW, CAP_CHEAP]})
    if p == "/resistors/list.json":
        return httpx.Response(200, json={"resistors": []})
    return httpx.Response(404, json={})


def client_with(handler, found=None, canonical=True):
    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(base_url="https://example.test",
                                    transport=transport)
    source = LcscMatcherSource(LcscAdapter(http_client))
    app.dependency_overrides[deps.get_matcher_source] = lambda: source
    app.dependency_overrides[deps.get_cached_service] = \
        lambda: StubCached(found=found, canonical=canonical)
    return TestClient(app)


def resistor_part():
    return part("R-ORIG", [offer("lcsc", "C100", "R-orig", price=0.001)])


def teardown_function():
    app.dependency_overrides.clear()


def test_equivalent_resolves_an_mpn_key_to_its_lcsc_offer():
    c = client_with(route, found=resistor_part())

    body = c.get("/api/equivalent/R-ORIG").json()

    assert body["original"]["lcsc"] == "C100"
    assert body["original"]["mpn_key"] == "R-ORIG"
    assert body["original"]["distributor"] == "lcsc"
    assert body["equivalent"]["lcsc"] == "C1"
    assert body["equivalent"]["mpn_key"] == body["equivalent"]["mpn"].upper()
    assert body["equivalent"]["percent_cheaper"] == 60
    assert body["reason"] is None


def test_equivalent_found_for_capacitor():
    cap = part("C-ORIG", [offer("lcsc", "C200", "C-orig", price=0.003)])
    c = client_with(cap_route, found=cap)

    body = c.get("/api/equivalent/C-ORIG").json()

    assert body["equivalent"]["lcsc"] == "C2"
    assert body["equivalent"]["percent_cheaper"] == 60


def test_equivalent_null_for_ic():
    ic = part("STM32F103C8T6", [offer("lcsc", "C8734")])
    c = client_with(route, found=ic)

    body = c.get("/api/equivalent/STM32F103C8T6").json()

    assert body["equivalent"] is None
    assert "resistors and capacitors" in body["reason"]


def test_a_part_with_no_lcsc_offer_gets_an_honest_null_not_an_error():
    mouser_only = part("MOUSER-ONLY", [offer("mouser", "511-X", "MOUSER-ONLY")])
    c = client_with(route, found=mouser_only)

    resp = c.get("/api/equivalent/MOUSER-ONLY")

    assert resp.status_code == 200
    body = resp.json()
    assert body["equivalent"] is None
    assert "LCSC" in body["reason"]
    assert body["original"]["lcsc"] is None
    assert body["original"]["distributor"] == "mouser"


def test_an_unknown_part_is_a_404():
    c = client_with(route, found=None)

    assert c.get("/api/equivalent/NOTHING").status_code == 404


def test_fold_drift_redirects():
    c = client_with(route, found=part("PART-A", [offer("lcsc", "C100", "PART-A")]),
                    canonical=False)

    resp = c.get("/api/equivalent/PART-A-TR", follow_redirects=False)

    assert resp.status_code == 302
    assert resp.headers["location"] == "/api/equivalent/PART-A"


def test_equivalent_timeout_504():
    def handler(request):
        raise httpx.ConnectTimeout("boom")

    c = client_with(handler, found=resistor_part())

    assert c.get("/api/equivalent/R-ORIG").status_code == 504


def test_equivalent_upstream_error_502():
    c = client_with(lambda req: httpx.Response(500, text="oops"),
                    found=resistor_part())

    assert c.get("/api/equivalent/R-ORIG").status_code == 502
