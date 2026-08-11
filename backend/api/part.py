"""GET /api/part/<lcsc_code>: spec §9 detail."""

from fastapi import APIRouter, Depends, HTTPException

from models.part import PartDetail
from services.datasource import PartDataSource, UpstreamError, UPSTREAM_STATUS
from services.deps import get_datasource, get_history_store
from services.matching import normalize_exact

router = APIRouter(prefix="/api")


@router.get("/part/{lcsc_code}", response_model=PartDetail)
async def get_part(
    lcsc_code: str,
    refresh: bool = False,
    ds: PartDataSource = Depends(get_datasource),
) -> PartDetail:
    try:
        detail = await ds.get_part(lcsc_code, refresh=refresh)
    except UpstreamError as exc:
        raise HTTPException(status_code=UPSTREAM_STATUS[exc.kind], detail=str(exc)) from exc
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Part {lcsc_code} not found")

    # A part someone looked at is a part worth tracking. Never fatal: the
    # detail response must not depend on the history store being reachable.
    store = get_history_store()
    if store is not None:
        try:
            await store.add_to_watchlist(normalize_exact(detail.mpn), detail.lcsc)
        except Exception:
            pass

    return detail
