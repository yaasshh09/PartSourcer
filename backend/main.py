"""PartSourcer API — application entry point.

Scaffold phase: exposes only GET /health. Routers for the real endpoints
(/api/search, /api/part/<code>, /api/part/<code>/equivalent) are added in
their respective build-order phases via app.include_router(...).
"""

from fastapi import FastAPI

app = FastAPI(title="PartSourcer API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
