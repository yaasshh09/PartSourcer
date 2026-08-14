"""A viewed part is watchlisted, and the write is never allowed to be fatal."""

import pytest
from fastapi.testclient import TestClient

from history.store import InMemoryHistoryStore
from main import app
from services import deps
from tests.stub_cached import StubCached, StubLcsc, offer, part


def _override(cached):
    app.dependency_overrides[deps.get_cached_service] = lambda: cached
    app.dependency_overrides[deps.get_lcsc_adapter] = lambda: StubLcsc()


@pytest.fixture
def client_and_store(monkeypatch):
    store = InMemoryHistoryStore()
    monkeypatch.setattr(deps, "_history_store", store, raising=False)
    _override(StubCached(found=part()))
    with TestClient(app) as client:
        yield client, store
    app.dependency_overrides.clear()


def test_detail_view_adds_part_to_watchlist(client_and_store):
    client, store = client_and_store
    assert client.get("/api/part/STM32F103C8T6").status_code == 200
    assert store.watchlist == {"STM32F103C8T6": "C8734"}


def test_missing_part_is_not_watchlisted(monkeypatch):
    store = InMemoryHistoryStore()
    monkeypatch.setattr(deps, "_history_store", store, raising=False)
    _override(StubCached(found=None))
    with TestClient(app) as client:
        assert client.get("/api/part/NOTHING").status_code == 404
    assert store.watchlist == {}
    app.dependency_overrides.clear()


def test_a_part_with_no_lcsc_offer_is_not_watchlisted(monkeypatch):
    """The watchlist keys on an LCSC code, so a part LCSC does not carry has
    nothing to record. Inventing a code for it would be a fabricated fact."""
    store = InMemoryHistoryStore()
    monkeypatch.setattr(deps, "_history_store", store, raising=False)
    _override(StubCached(found=part(offers=[offer("mouser", "511-X")])))
    with TestClient(app) as client:
        assert client.get("/api/part/STM32F103C8T6").status_code == 200
    assert store.watchlist == {}
    app.dependency_overrides.clear()


def test_detail_still_works_with_no_history_store(monkeypatch):
    monkeypatch.setattr(deps, "_history_store", None, raising=False)
    _override(StubCached(found=part()))
    with TestClient(app) as client:
        assert client.get("/api/part/STM32F103C8T6").status_code == 200
    app.dependency_overrides.clear()
