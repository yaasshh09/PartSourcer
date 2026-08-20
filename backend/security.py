"""Edge hardening: response headers, request body ceiling, inbound rate limit.

Written as plain ASGI middleware rather than BaseHTTPMiddleware so a rejected
request never has to build a full request object first, and so the headers get
stamped on every response including the ones these middlewares generate
themselves.

Everything here is deliberately independent of the routes. A header that only
lands when a handler remembers to set it is a header that goes missing the
first time someone adds a route.
"""

import json
from typing import Awaitable, Callable, Iterable

from starlette.datastructures import Headers, MutableHeaders

from services.ratelimit import RateLimiter

Scope = dict
Receive = Callable[[], Awaitable[dict]]
Send = Callable[[dict], Awaitable[None]]

#: Sent on every response. Values chosen for a JSON API that no browser should
#: ever frame, script, or treat as anything but data.
BASE_HEADERS: dict[str, str] = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "strict-origin-when-cross-origin",
    "permissions-policy": ("accelerometer=(), autoplay=(), camera=(), "
                           "display-capture=(), encrypted-media=(), "
                           "geolocation=(), gyroscope=(), magnetometer=(), "
                           "microphone=(), midi=(), payment=(), usb=()"),
    "cross-origin-opener-policy": "same-origin",
    # The API is meant to be readable from the site's own origin and from
    # anyone's curl. same-origin here would break the documented split-host
    # deploy (frontend on one host, backend on another) for no gain, because
    # every response is public data with no cookie attached to steal.
    "cross-origin-resource-policy": "cross-origin",
}

#: A JSON API renders nothing, loads nothing and frames nothing, so it gets
#: the strictest policy CSP can express.
API_CSP = ("default-src 'none'; frame-ancestors 'none'; base-uri 'none'; "
           "form-action 'none'; sandbox")

HSTS = "max-age=31536000; includeSubDomains"

#: Swagger UI pulls its own JS and CSS, so the API policy would blank it. These
#: only exist off production (see config.docs_enabled), and skipping the policy
#: on them is narrower than weakening the policy everywhere.
DOCS_PATHS = frozenset({"/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"})


async def _send_json(send: Send, status: int, detail: str,
                     extra: dict[str, str] | None = None) -> None:
    """A rejection shaped exactly like the app's other errors."""
    body = json.dumps({"detail": detail}).encode()
    headers = [(b"content-type", b"application/json"),
               (b"content-length", str(len(body)).encode())]
    for key, value in (extra or {}).items():
        headers.append((key.encode(), value.encode()))
    await send({"type": "http.response.start", "status": status,
                "headers": headers})
    await send({"type": "http.response.body", "body": body})


def _is_https(scope: Scope) -> bool:
    """True when the browser's leg of the connection was TLS.

    The hop into the app is plain HTTP on every platform that terminates TLS
    for us, so the forwarded header is the only witness. HSTS on a plain-HTTP
    response is ignored by browsers anyway; this keeps it off local dev where
    it would be a footgun if the port were ever reused.
    """
    if scope.get("scheme") == "https":
        return True
    return Headers(scope=scope).get("x-forwarded-proto", "").split(",")[0].strip() == "https"


class SecurityHeadersMiddleware:
    """Stamps the fixed header set on every response, including error ones."""

    def __init__(self, app, docs_paths: Iterable[str] = DOCS_PATHS):
        self.app = app
        self._docs_paths = frozenset(docs_paths)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        secure = _is_https(scope)
        relaxed = scope.get("path", "") in self._docs_paths

        async def send_wrapper(message: dict) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in BASE_HEADERS.items():
                    if relaxed and name == "x-frame-options":
                        continue
                    headers.setdefault(name, value)
                if not relaxed:
                    headers.setdefault("content-security-policy", API_CSP)
                if secure:
                    headers.setdefault("strict-transport-security", HSTS)
            await send(message)

        await self.app(scope, receive, send_wrapper)


class BodySizeLimitMiddleware:
    """Refuses a request body larger than `max_bytes` before the app sees it.

    This app takes no uploads and its one POST carries no body at all, so the
    ceiling is small on purpose: it exists so that adding a body-reading route
    later cannot quietly turn into an unbounded memory read.
    """

    def __init__(self, app, max_bytes: int):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method") in ("GET", "HEAD", "OPTIONS"):
            return await self.app(scope, receive, send)

        declared = Headers(scope=scope).get("content-length")
        if declared and declared.isdigit() and int(declared) > self.max_bytes:
            return await _send_json(send, 413, "request body too large")

        # Buffered rather than streamed so the rejection can still be a clean
        # 413: once the app has started its own response there is no way to
        # replace it. Safe because the cap is kilobytes, not megabytes.
        chunks: list[bytes] = []
        total = 0
        more = True
        while more:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            total += len(chunk)
            if total > self.max_bytes:
                return await _send_json(send, 413, "request body too large")
            chunks.append(chunk)
            more = message.get("more_body", False)

        body = b"".join(chunks)
        delivered = False

        async def replay() -> dict:
            nonlocal delivered
            if delivered:
                return {"type": "http.disconnect"}
            delivered = True
            return {"type": "http.request", "body": body, "more_body": False}

        await self.app(scope, replay, send)


def client_key(scope: Scope) -> str:
    """Who to count this request against.

    The left-most X-Forwarded-For entry is whatever the client typed, so
    trusting it hands every attacker an unlimited supply of fresh buckets.
    Only headers the platform itself writes are consulted, and the socket peer
    is the fallback.
    """
    headers = Headers(scope=scope)
    for name in ("x-vercel-forwarded-for", "x-real-ip", "fly-client-ip",
                 "cf-connecting-ip"):
        value = headers.get(name, "").split(",")[0].strip()
        if value:
            return value
    client = scope.get("client")
    return client[0] if client else "unknown"


class RateLimitMiddleware:
    def __init__(self, app, limiter: RateLimiter,
                 exempt_paths: Iterable[str] = ("/health",)):
        self.app = app
        self.limiter = limiter
        self._exempt = frozenset(exempt_paths)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("path", "") in self._exempt:
            return await self.app(scope, receive, send)
        # A preflight is the browser asking permission, not a call on the API.
        # Counting it would halve every cross-origin client's real budget.
        if scope.get("method") == "OPTIONS":
            return await self.app(scope, receive, send)

        result = self.limiter.check(client_key(scope))
        if not result.allowed:
            return await _send_json(
                send, 429, "too many requests, slow down",
                {"retry-after": str(result.retry_after)})
        await self.app(scope, receive, send)
