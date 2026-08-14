"""GET /api/part/{mpn_key} over a stubbed CachedPartService."""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

import services.deps as deps
from main import app
from services.adapters.base import RawListing
from tests.stub_cached import StubCached, StubLcsc, offer, part

AS_OF = datetime(2026, 8, 14, 9, 0, tzinfo=timezone.utc)

C8734 = RawListing(distributor="lcsc", sku="C8734", mpn="STM32F103C8T6",
                   brand=None, package="LQFP-48", description="ARM MCU",
                   stock=214596, in_stock=True, price=1.04, currency="USD",
                   price_breaks=None, datasheet_url=None, product_url=None,
                   as_of=AS_OF)


def teardown_function():
    app.dependency_overrides.clear()


def client_over(cached, lcsc=None):
    app.dependency_overrides[deps.get_cached_service] = lambda: cached
    app.dependency_overrides[deps.get_lcsc_adapter] = \
        lambda: lcsc if lcsc is not None else StubLcsc()
    return TestClient(app)


@pytest.fixture
def client():
    """A warmed cache: C8734 resolves, and any MPN lookup finds the part."""
    return client_over(StubCached(found=part(), skus={"C8734": "STM32F103C8T6"}),
                       StubLcsc({"C8734": C8734}))


@pytest.fixture
def client_fold_drift():
    return client_over(StubCached(found=part(), canonical=False))


@pytest.fixture
def client_empty():
    return client_over(StubCached(found=None))


def test_detail_returns_the_part_and_its_sources(client):
    body = client.get("/api/part/STM32F103C8T6").json()

    assert body["part"]["mpn_key"] == "STM32F103C8T6"
    assert body["part"]["offers"][0]["sku"] == "C8734"
    assert {s["distributor"] for s in body["sources"]} == {"lcsc", "mouser", "digikey"}


def test_a_slash_bearing_mpn_resolves(client):
    assert client.get("/api/part/LM358P/NOPB").status_code == 200


def test_a_legacy_lcsc_code_redirects_to_the_canonical_mpn(client):
    resp = client.get("/api/part/C8734", follow_redirects=False)

    assert resp.status_code == 302
    assert resp.headers["location"] == "/api/part/STM32F103C8T6"


def test_a_code_shaped_string_that_is_not_a_sku_is_treated_as_an_mpn(client):
    """2SC1815 is catalogued as C1815, so ^C\\d+$ is not proof of a SKU. When
    the code does not resolve, fall through rather than 404."""
    resp = client.get("/api/part/C1815", follow_redirects=False)

    assert resp.status_code in (200, 404)
    assert resp.status_code != 302


def test_a_trailing_character_makes_it_an_mpn_not_a_code(client):
    resp = client.get("/api/part/C8734X", follow_redirects=False)

    assert resp.status_code != 302


def test_fold_drift_redirects_to_the_canonical_key(client_fold_drift):
    resp = client_fold_drift.get("/api/part/STM32F103C8T6-TR",
                                 follow_redirects=False)

    assert resp.status_code == 302
    assert resp.headers["location"] == "/api/part/STM32F103C8T6"


def test_a_missing_part_is_a_404(client_empty):
    assert client_empty.get("/api/part/NOTHING").status_code == 404


def test_an_unresolvable_legacy_code_falls_through_to_a_404(client_empty):
    resp = client_empty.get("/api/part/C99999999", follow_redirects=False)

    assert resp.status_code == 404


def test_a_part_with_no_lcsc_offer_still_answers():
    c = client_over(StubCached(found=part(offers=[offer("mouser", "511-X")])))

    body = c.get("/api/part/STM32F103C8T6").json()

    assert body["part"]["offers"][0]["distributor"] == "mouser"
