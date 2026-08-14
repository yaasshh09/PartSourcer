"""Route-presence guard: every public route must exist in the OpenAPI schema."""

from fastapi.testclient import TestClient

from main import app


def test_openapi_lists_every_public_route():
    paths = TestClient(app).get("/openapi.json").json()["paths"]
    assert "/health" in paths
    assert "/api/search" in paths
    assert "/api/part/{mpn_key}" in paths
    assert "/api/equivalent/{mpn_key}" in paths
