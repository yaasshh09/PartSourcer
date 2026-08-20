"""Headers, the body ceiling and the rate limit, tested as ASGI middleware.

Wrapped around a stub app rather than the real one so a failure names the
middleware instead of whichever route happened to be involved. One test at the
bottom checks the wiring on the app itself, because middleware that works in
isolation and is never mounted protects nothing.
"""

import json

from fastapi.testclient import TestClient

from main import app
from security import (API_CSP, BASE_HEADERS, BodySizeLimitMiddleware,
                      RateLimitMiddleware, SecurityHeadersMiddleware,
                      client_key)
from services.ratelimit import RateLimiter


async def echo_app(scope, receive, send):
    """Reports how many body bytes actually reached the application."""
    body = b""
    if scope["method"] not in ("GET", "HEAD"):
        while True:
            message = await receive()
            body += message.get("body", b"")
            if not message.get("more_body"):
                break
    payload = json.dumps({"received": len(body)}).encode()
    await send({"type": "http.response.start", "status": 200,
                "headers": [(b"content-type", b"application/json")]})
    await send({"type": "http.response.body", "body": payload})


def test_every_response_carries_the_fixed_header_set():
    client = TestClient(SecurityHeadersMiddleware(echo_app))
    headers = client.get("/anything").headers
    for name, value in BASE_HEADERS.items():
        assert headers[name] == value
    assert headers["content-security-policy"] == API_CSP


def test_hsts_only_on_a_connection_the_browser_reached_over_tls():
    client = TestClient(SecurityHeadersMiddleware(echo_app))
    assert "strict-transport-security" not in client.get("/x").headers
    forwarded = client.get("/x", headers={"X-Forwarded-Proto": "https"})
    assert forwarded.headers["strict-transport-security"].startswith("max-age=31536000")


def test_docs_keep_the_headers_that_do_not_blank_swagger():
    """Swagger loads its own assets, so the API policy would leave it empty."""
    client = TestClient(SecurityHeadersMiddleware(echo_app))
    headers = client.get("/docs").headers
    assert "content-security-policy" not in headers
    assert "x-frame-options" not in headers
    assert headers["x-content-type-options"] == "nosniff"


def test_oversized_body_is_refused_before_the_app_reads_it():
    client = TestClient(BodySizeLimitMiddleware(echo_app, max_bytes=100))
    resp = client.post("/x", content=b"a" * 500)
    assert resp.status_code == 413
    assert resp.json() == {"detail": "request body too large"}


def test_a_lying_content_length_does_not_get_the_body_through():
    """The declared length is a fast path, not the check."""
    client = TestClient(BodySizeLimitMiddleware(echo_app, max_bytes=100))
    resp = client.post("/x", content=b"a" * 500,
                       headers={"Content-Length": "10"})
    assert resp.status_code == 413


def test_a_body_within_the_ceiling_reaches_the_app_intact():
    client = TestClient(BodySizeLimitMiddleware(echo_app, max_bytes=100))
    resp = client.post("/x", content=b"a" * 90)
    assert resp.status_code == 200
    assert resp.json() == {"received": 90}


def test_get_requests_skip_the_buffer_entirely():
    client = TestClient(BodySizeLimitMiddleware(echo_app, max_bytes=1))
    assert client.get("/x").status_code == 200


def test_rate_limit_rejects_with_429_and_a_retry_after():
    limiter = RateLimiter(limit=2, window_secs=60)
    client = TestClient(RateLimitMiddleware(echo_app, limiter=limiter))
    assert client.get("/api/search").status_code == 200
    assert client.get("/api/search").status_code == 200
    blocked = client.get("/api/search")
    assert blocked.status_code == 429
    assert blocked.json() == {"detail": "too many requests, slow down"}
    assert int(blocked.headers["retry-after"]) >= 1


def test_health_is_never_rate_limited():
    """An uptime check runs on a schedule and must not lock itself out."""
    limiter = RateLimiter(limit=1, window_secs=60)
    client = TestClient(RateLimitMiddleware(echo_app, limiter=limiter))
    assert [client.get("/health").status_code for _ in range(5)] == [200] * 5


def test_preflight_is_not_charged_to_the_budget():
    limiter = RateLimiter(limit=1, window_secs=60)
    client = TestClient(RateLimitMiddleware(echo_app, limiter=limiter))
    client.options("/api/search")
    assert client.get("/api/search").status_code == 200


def test_client_key_ignores_the_spoofable_forwarded_for_header():
    """Trusting it would hand an attacker an unlimited supply of buckets."""
    scope = {"type": "http", "client": ("203.0.113.9", 1234),
             "headers": [(b"x-forwarded-for", b"1.2.3.4")]}
    assert client_key(scope) == "203.0.113.9"


def test_client_key_prefers_a_header_the_platform_writes():
    scope = {"type": "http", "client": ("10.0.0.1", 1234),
             "headers": [(b"x-forwarded-for", b"1.2.3.4"),
                         (b"x-vercel-forwarded-for", b"198.51.100.7")]}
    assert client_key(scope) == "198.51.100.7"


def test_the_real_app_actually_mounts_the_headers():
    headers = TestClient(app).get("/health").headers
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert headers["content-security-policy"] == API_CSP
    assert headers["referrer-policy"] == "strict-origin-when-cross-origin"
