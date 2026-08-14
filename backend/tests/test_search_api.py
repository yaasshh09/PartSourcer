"""GET /api/search over a stubbed CachedPartService."""

import pytest
from fastapi.testclient import TestClient

import services.deps as deps
from main import app
from services.datasource import UpstreamError
from tests.stub_cached import ALL_OK, StubCached, part, status


def teardown_function():
    app.dependency_overrides.clear()


def client_over(stub):
    app.dependency_overrides[deps.get_cached_service] = lambda: stub
    return TestClient(app)


@pytest.fixture
def client():
    return client_over(StubCached(found=part()))


@pytest.fixture
def client_partial():
    return client_over(StubCached(
        found=part(),
        sources=[status("lcsc"),
                 status("mouser", "quota_exhausted", "daily limit reached"),
                 status("digikey", "disabled", "no credentials configured")]))


@pytest.fixture
def client_all_down():
    return client_over(StubCached(error=UpstreamError("unavailable", "all down")))


def test_search_returns_the_v2_shape(client):
    body = client.get("/api/search?q=stm32").json()

    assert body["page"] == 1 and body["query"] == "stm32"
    assert body["results"][0]["mpn_key"] == "STM32F103C8T6"
    assert body["results"][0]["offers"][0]["distributor"] == "lcsc"
    assert {s["distributor"] for s in body["sources"]} == {"lcsc", "mouser", "digikey"}


def test_a_part_carries_its_oldest_offer_as_its_as_of(client):
    body = client.get("/api/search?q=stm32").json()

    assert body["results"][0]["as_of"].startswith("2026-08-14T09:00")


def test_a_partial_failure_is_a_200_with_an_honest_sources_block(client_partial):
    resp = client_partial.get("/api/search?q=stm32")

    assert resp.status_code == 200
    mouser = next(s for s in resp.json()["sources"] if s["distributor"] == "mouser")
    assert mouser["state"] == "quota_exhausted"


def test_every_adapter_failing_is_still_an_upstream_error(client_all_down):
    assert client_all_down.get("/api/search?q=stm32").status_code == 502


def test_page_is_echoed_back(client):
    assert client.get("/api/search?q=stm32&page=3").json()["page"] == 3


def test_page_zero_is_rejected(client):
    assert client.get("/api/search?q=stm32&page=0").status_code == 422


def test_sources_are_reported_even_with_no_results():
    c = client_over(StubCached(found=None, sources=list(ALL_OK)))

    body = c.get("/api/search?q=nothing").json()

    assert body["results"] == []
    assert len(body["sources"]) == 3
