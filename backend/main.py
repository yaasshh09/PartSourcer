"""PartSourcer API — application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from api.equivalent import router as equivalent_router
from api.part import router as part_router
from api.search import router as search_router
from services import deps


@asynccontextmanager
async def lifespan(app: FastAPI):
    await deps.startup()
    try:
        yield
    finally:
        await deps.shutdown()


app = FastAPI(title="PartSourcer API", lifespan=lifespan)


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
app.include_router(part_router)
app.include_router(equivalent_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
