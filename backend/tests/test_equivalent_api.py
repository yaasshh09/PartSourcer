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
from tests.stub_cached import StubCached, StubLcsc, offer, part

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
    # /api/search answers two different reads: lookup_sku resolves a code to
    # an identity, and canonical_part re-reads a part by MPN to price it. So
    # the mock has to answer for the candidate too, not just the original.
    p = request.url.path
    if p == "/api/search":
        # Upper-cased: canonical reads go out as normalize_exact of the MPN,
        # which is the same string the search and detail paths send.
        q = request.url.params.get("q", "").upper()
        if "8734" in q or "STM32" in q:
            return httpx.Response(200, json={"components": [IC_ROW]})
        if "R-CHEAP" in q:
            return httpx.Response(200, json={"components": [RES_CHEAP]})
        return httpx.Response(200, json={"components": [RES_ROW]})
    if p == "/resistors/list.json":
        return httpx.Response(200, json={"resistors": [RES_ROW, RES_CHEAP]})
    if p == "/capacitors/list.json":
        return httpx.Response(200, json={"capacitors": []})
    return httpx.Response(404, json={})


def cap_route(request):
    p = request.url.path
    if p == "/api/search":
        q = request.url.params.get("q", "").upper()
        if "C-CHEAP" in q:
            return httpx.Response(200, json={"components": [CAP_CHEAP]})
        return httpx.Response(200, json={"components": [CAP_ROW]})
    if p == "/capacitors/list.json":
        return httpx.Response(200, json={"capacitors": [CAP_ROW, CAP_CHEAP]})
    if p == "/resistors/list.json":
        return httpx.Response(200, json={"resistors": []})
    return httpx.Response(404, json={})


def client_with(handler, found=None, canonical=True, skus=None, lcsc=None):
    """`skus` seeds the cache's SKU index, `lcsc` replaces the adapter that
    legacy-code resolution falls back to. Left unset, the adapter is the real
    one over `handler`, so resolution goes upstream through the mock."""
    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(base_url="https://example.test",
                                    transport=transport)
    adapter = LcscAdapter(http_client)
    source = LcscMatcherSource(adapter)
    app.dependency_overrides[deps.get_matcher_source] = lambda: source
    app.dependency_overrides[deps.get_lcsc_adapter] = \
        lambda: lcsc if lcsc is not None else adapter
    app.dependency_overrides[deps.get_cached_service] = \
        lambda: StubCached(found=found, canonical=canonical, skus=skus)
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


def test_an_unpriced_offer_does_not_break_picking_one_to_quote():
    """Prices are optional now, and ordering None against a float used to
    raise. An unpriced offer sorts last instead: it is the worst one to
    quote, not a reason to fail the request."""
    mixed = part("MOUSER-ONLY", [offer("mouser", "511-X", "MOUSER-ONLY",
                                       price=None),
                                 offer("digikey", "DK-1", "MOUSER-ONLY",
                                       price=2.5)])
    c = client_with(route, found=mixed)

    resp = c.get("/api/equivalent/MOUSER-ONLY")

    assert resp.status_code == 200
    body = resp.json()
    assert body["original"]["price_usd"] == 2.5
    assert body["original"]["distributor"] == "digikey"


def test_an_offer_with_no_price_anywhere_still_answers_honestly():
    only_unpriced = part("MOUSER-ONLY", [offer("mouser", "511-X",
                                               "MOUSER-ONLY", price=None)])
    c = client_with(route, found=only_unpriced)

    body = c.get("/api/equivalent/MOUSER-ONLY").json()

    assert body["equivalent"] is None
    assert body["original"]["price_usd"] is None


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


# -- legacy LCSC codes -------------------------------------------------------
# /api/part/C7593 resolves an old-style code to its canonical MPN and
# redirects. This route did not, so every legacy link 404'd on the one feature
# the project exists for. Both routes now share api/legacy.py.

def test_a_legacy_lcsc_code_resolves_from_the_cache():
    c = client_with(route, found=resistor_part(), skus={"C100": "R-ORIG"},
                    lcsc=StubLcsc())

    resp = c.get("/api/equivalent/C100", follow_redirects=False)

    assert resp.status_code == 302
    assert resp.headers["location"] == "/api/equivalent/R-ORIG"


def test_a_legacy_lcsc_code_falls_back_to_upstream_when_the_cache_misses():
    """The cache only knows codes it has already seen, so a cold backend has
    to ask LCSC directly or the redirect works only after a warm-up."""
    c = client_with(route, found=resistor_part())

    resp = c.get("/api/equivalent/C100", follow_redirects=False)

    assert resp.status_code == 302
    assert resp.headers["location"] == "/api/equivalent/R-ORIG"


def test_a_code_shaped_mpn_that_resolves_to_nothing_is_still_tried_as_an_mpn():
    """2SC1815 is catalogued as C1815, so a code-shaped string is not proof of
    a SKU. Redirecting on shape alone would 404 a real part."""
    c = client_with(lambda req: httpx.Response(200, json={"components": []}),
                    found=None, lcsc=StubLcsc())

    resp = c.get("/api/equivalent/C1815", follow_redirects=False)

    assert resp.status_code == 404


def test_a_legacy_code_reports_an_upstream_failure_honestly_not_as_a_500():
    """Resolving the code is an upstream call like any other, so it owes the
    caller the same 504 the rest of the route gives, not an opaque 500."""
    def handler(request):
        raise httpx.ConnectTimeout("boom")

    c = client_with(handler, found=resistor_part())

    assert c.get("/api/equivalent/C100").status_code == 504
