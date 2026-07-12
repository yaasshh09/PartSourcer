"""Route-presence guard: all four v1 routes must exist in the OpenAPI schema."""

from fastapi.testclient import TestClient

from main import app


def test_openapi_lists_all_v1_routes():
    paths = TestClient(app).get("/openapi.json").json()["paths"]
    assert "/health" in paths
    assert "/api/search" in paths
    assert "/api/part/{lcsc_code}" in paths
    assert "/api/part/{lcsc_code}/equivalent" in paths
