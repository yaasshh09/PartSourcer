"""Ceilings on what a caller may put in a query string or a path.

These are cost controls, not sanitisers. Every one of them is checked before
the request can reach the cache or a metered distributor, so a rejected call
costs nothing downstream. The stub records whether it was reached at all,
which is the part that actually matters.
"""

import pytest
from fastapi.testclient import TestClient

import services.deps as deps
from api.validation import MAX_KEY_LEN, MAX_PAGE, MAX_QUERY_LEN
from main import app
from tests.stub_cached import StubCached, StubLcsc, part


class RecordingStub(StubCached):
    """A StubCached that remembers whether the route got as far as calling it."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.calls = 0

    async def search(self, *args, **kwargs):
        self.calls += 1
        return await super().search(*args, **kwargs)

    async def lookup(self, *args, **kwargs):
        self.calls += 1
        return await super().lookup(*args, **kwargs)


def teardown_function():
    app.dependency_overrides.clear()


@pytest.fixture
def stub():
    s = RecordingStub(found=part())
    app.dependency_overrides[deps.get_cached_service] = lambda: s
    # The part and equivalent routes also take the adapter and the matcher
    # source; neither is reached by a rejected request, but FastAPI resolves
    # every dependency before the handler body runs.
    app.dependency_overrides[deps.get_lcsc_adapter] = StubLcsc
    app.dependency_overrides[deps.get_matcher_source] = lambda: None
    return s


@pytest.fixture
def client(stub):
    return TestClient(app)


def test_a_query_at_the_ceiling_is_served(client, stub):
    assert client.get(f"/api/search?q={'x' * MAX_QUERY_LEN}").status_code == 200
    assert stub.calls == 1


def test_an_oversized_query_is_refused_without_touching_upstream(client, stub):
    resp = client.get(f"/api/search?q={'x' * (MAX_QUERY_LEN + 1)}")
    assert resp.status_code == 422
    assert stub.calls == 0


def test_deep_paging_is_refused_without_touching_upstream(client, stub):
    assert client.get(f"/api/search?q=ne555&page={MAX_PAGE}").status_code == 200
    resp = client.get(f"/api/search?q=ne555&page={MAX_PAGE + 1}")
    assert resp.status_code == 422
    assert stub.calls == 1


def test_page_zero_and_negative_pages_are_still_refused(client):
    assert client.get("/api/search?q=ne555&page=0").status_code == 422
    assert client.get("/api/search?q=ne555&page=-1").status_code == 422


@pytest.mark.parametrize("route", ["/api/part", "/api/equivalent"])
def test_an_oversized_part_key_is_refused_on_every_route(client, stub, route):
    resp = client.get(f"{route}/{'A' * (MAX_KEY_LEN + 1)}")
    assert resp.status_code == 422
    assert "mpn_key" in resp.json()["detail"]
    assert stub.calls == 0


def test_a_realistic_part_key_still_works(client, stub):
    """The ceiling has to clear a real MPN with a package suffix on it."""
    assert client.get("/api/part/LM358P/NOPB").status_code == 200
    assert stub.calls == 1
