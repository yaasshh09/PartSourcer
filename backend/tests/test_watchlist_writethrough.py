from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from history.store import InMemoryHistoryStore
from main import app
from models.part import PartDetail
from services import deps
from services.datasource import PartDataSource

FIXED = datetime(2026, 8, 8, 3, 0, tzinfo=timezone.utc)


class StubDs(PartDataSource):
    async def search(self, query, page, refresh=False):
        return []

    async def get_part(self, lcsc_code, refresh=False):
        if lcsc_code != "C8734":
            return None
        return PartDetail(lcsc="C8734", mpn="STM32F103C8T6", brand=None,
                          package="LQFP-48", description="", stock=1,
                          price_usd=1.0, price_breaks=None,
                          stock_breakdown=None, is_basic=True,
                          is_preferred=None, datasheet_url=None, as_of=FIXED)

    async def list_parametric(self, category, package, resistance_ohms=None):
        return []


@pytest.fixture
def client_and_store(monkeypatch):
    store = InMemoryHistoryStore()
    monkeypatch.setattr(deps, "_history_store", store, raising=False)
    app.dependency_overrides[deps.get_datasource] = lambda: StubDs()
    with TestClient(app) as client:
        yield client, store
    app.dependency_overrides.clear()


def test_detail_view_adds_part_to_watchlist(client_and_store):
    client, store = client_and_store
    assert client.get("/api/part/C8734").status_code == 200
    assert store.watchlist == {"STM32F103C8T6": "C8734"}


def test_missing_part_is_not_watchlisted(client_and_store):
    client, store = client_and_store
    assert client.get("/api/part/C0000").status_code == 404
    assert store.watchlist == {}


def test_detail_still_works_with_no_history_store(monkeypatch):
    monkeypatch.setattr(deps, "_history_store", None, raising=False)
    app.dependency_overrides[deps.get_datasource] = lambda: StubDs()
    with TestClient(app) as client:
        assert client.get("/api/part/C8734").status_code == 200
    app.dependency_overrides.clear()
