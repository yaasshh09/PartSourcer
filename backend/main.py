"""PartSourcer API — application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

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
app.include_router(search_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
