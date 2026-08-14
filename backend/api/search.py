"""GET /api/search: the multi-distributor search surface."""

from fastapi import APIRouter, Depends, HTTPException, Query

from cache.cached_part_service import CachedPartService
from models.offer import SearchResponse
from services.datasource import UPSTREAM_STATUS, UpstreamError
from services.deps import get_cached_service

router = APIRouter(prefix="/api")


@router.get("/search", response_model=SearchResponse)
async def search(
    q: str = "",
    page: int = Query(1, ge=1),
    refresh: bool = False,
    cached: CachedPartService = Depends(get_cached_service),
) -> SearchResponse:
    # A partial failure is a 200 with an honest sources block. UpstreamError
    # only reaches here when every callable distributor failed, because
    # PartService turns a single source's failure into a status.
    try:
        return await cached.search(q, page, refresh=refresh)
    except UpstreamError as exc:
        raise HTTPException(status_code=UPSTREAM_STATUS[exc.kind],
                            detail=str(exc)) from exc
