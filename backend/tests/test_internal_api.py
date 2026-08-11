import pytest
from fastapi.testclient import TestClient

import config
from history.store import InMemoryHistoryStore
from main import app
from services import deps


@pytest.fixture
def store_and_client(monkeypatch):
    store = InMemoryHistoryStore()
    monkeypatch.setattr(config.settings, "recorder_token", "s3cret")
    monkeypatch.setattr(deps, "_history_store", store, raising=False)
    with TestClient(app) as client:
        yield store, client


def test_missing_token_is_401(store_and_client):
    _, client = store_and_client
    assert client.post("/api/internal/record").status_code == 401


def test_wrong_token_is_401(store_and_client):
    _, client = store_and_client
    resp = client.post("/api/internal/record", headers={"X-Recorder-Token": "nope"})
    assert resp.status_code == 401


def test_correct_token_returns_summary(store_and_client):
    _, client = store_and_client
    resp = client.post("/api/internal/record", headers={"X-Recorder-Token": "s3cret"})
    assert resp.status_code == 200
    assert resp.json() == {"recorded": 0, "skipped": 0, "errors": 0}


def test_disabled_when_no_token_configured(monkeypatch):
    monkeypatch.setattr(config.settings, "recorder_token", None)
    with TestClient(app) as client:
        resp = client.post("/api/internal/record", headers={"X-Recorder-Token": "x"})
        assert resp.status_code == 503
        assert resp.json() == {"detail": "recorder is not configured"}
