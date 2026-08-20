"""PartSourcer API: application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings
from security import (BodySizeLimitMiddleware, RateLimitMiddleware,
                      SecurityHeadersMiddleware)

from api.equivalent import router as equivalent_router
from api.internal import router as internal_router
from api.part import router as part_router
from api.search import router as search_router
from services import deps
from services.ratelimit import RateLimiter


@asynccontextmanager
async def lifespan(app: FastAPI):
    await deps.startup()
    try:
        yield
    finally:
        await deps.shutdown()


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s")

# httpx logs every request line, URL and all, at INFO. Mouser takes its API key
# as a query parameter, so at root's INFO level that line writes a live secret
# into the log, and on a hosted backend into the provider's log stream. Warnings
# and above still come through, so a genuine client failure is still reported.
logging.getLogger("httpx").setLevel(logging.WARNING)

log = logging.getLogger("partsourcer.security")

# Loud and once, at import, so a bad value is visible in the deploy log rather
# than discovered by whoever exploits it. Reported instead of raised: see
# Settings.safe_cors_origins for why a wildcard must not black out the site.
for _problem in settings.security_problems():
    log.error("insecure configuration: %s", _problem)

# The docs and the schema are a free map of every route and parameter shape.
# Nothing on a deployed host reads them, so they only exist in development.
_docs = "/docs" if settings.docs_enabled else None
_redoc = "/redoc" if settings.docs_enabled else None
_schema = "/openapi.json" if settings.docs_enabled else None

app = FastAPI(title="PartSourcer API", lifespan=lifespan,
              docs_url=_docs, redoc_url=_redoc, openapi_url=_schema)

# Order matters and reads backwards: add_middleware pushes onto the front of
# the stack, so the last one added is the outermost. Wanted, outside in:
# headers (stamps every response, including the two rejections below), CORS
# (so a browser can actually read a 429 instead of seeing a CORS error), the
# body ceiling, then the rate limit closest to the app.
app.add_middleware(
    RateLimitMiddleware,
    limiter=RateLimiter(limit=settings.rate_limit_requests,
                        window_secs=settings.rate_limit_window_secs,
                        max_keys=settings.rate_limit_max_keys))
app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_request_bytes)
app.add_middleware(
    CORSMiddleware,
    # Sanitised, not raw: a wildcard or a plain-HTTP origin never reaches the
    # browser even if one is sitting in the environment.
    allow_origins=settings.safe_cors_origins(),
    allow_methods=["GET"],
    # Named rather than "*" so a request carrying an unexpected header is a
    # failed preflight instead of something the API agreed to in advance.
    allow_headers=["Accept", "Content-Type"],
    allow_credentials=False,
)
app.add_middleware(SecurityHeadersMiddleware)


@app.exception_handler(RequestValidationError)
async def _validation_handler(request: Request,
                              exc: RequestValidationError) -> JSONResponse:
    """Flatten FastAPI's validation error list to a single {"detail": str}."""
    errors = exc.errors()
    if errors:
        first = errors[0]
        parts = [str(p) for p in first.get("loc", ()) if p not in ("query", "body", "path")]
        loc = ".".join(parts)
        msg = first.get("msg", "invalid request")
        detail = f"{loc}: {msg}" if loc else msg
    else:
        detail = "invalid request"
    return JSONResponse(status_code=422, content={"detail": detail})


@app.exception_handler(Exception)
async def _unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
    """Any uncaught error -> clean 500; never leak internals."""
    return JSONResponse(status_code=500, content={"detail": "internal server error"})


app.include_router(search_router)
app.include_router(equivalent_router)
app.include_router(part_router)
app.include_router(internal_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
