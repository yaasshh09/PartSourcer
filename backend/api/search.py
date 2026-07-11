"""GET /api/search — spec §9."""

from fastapi import APIRouter, Depends, HTTPException, Query

from models.search import SearchResponse
from services.datasource import PartDataSource, UpstreamError, UPSTREAM_STATUS
from services.deps import get_datasource

router = APIRouter(prefix="/api")


@router.get("/search", response_model=SearchResponse)
async def search(
    q: str = "",
    page: int = Query(1, ge=1),
    refresh: bool = False,
    ds: PartDataSource = Depends(get_datasource),
) -> SearchResponse:
    try:
        results = await ds.search(q, page, refresh=refresh)
    except UpstreamError as exc:
        raise HTTPException(status_code=UPSTREAM_STATUS[exc.kind], detail=str(exc)) from exc
    return SearchResponse(page=page, results=results)
