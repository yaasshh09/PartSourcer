"""POST /api/internal/record: nightly history capture (SP2a).

Not part of the public API. Protected by a shared token; returns 503 when
the recorder is not configured so a misconfigured deploy fails loudly
rather than silently accepting anonymous writes.
"""

import secrets

from fastapi import APIRouter, Depends, Header, HTTPException

from config import settings
from history.recorder import record_watchlist
from services.datasource import PartDataSource
from services.deps import get_datasource, get_history_store

router = APIRouter(prefix="/api/internal")


@router.post("/record")
async def record(
    x_recorder_token: str | None = Header(default=None),
    ds: PartDataSource = Depends(get_datasource),
) -> dict[str, int]:
    expected = settings.recorder_token
    store = get_history_store()
    if not expected or store is None:
        raise HTTPException(status_code=503, detail="recorder is not configured")
    if not x_recorder_token or not secrets.compare_digest(x_recorder_token, expected):
        raise HTTPException(status_code=401, detail="invalid recorder token")

    summary = await record_watchlist(
        ds, store,
        batch_size=settings.recorder_batch_size,
        concurrency=settings.recorder_concurrency)
    return {"recorded": summary.recorded, "skipped": summary.skipped,
            "errors": summary.errors}
