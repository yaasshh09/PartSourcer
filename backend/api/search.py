"""GET /api/search — spec §9."""

from fastapi import APIRouter, Depends, HTTPException, Query

from models.search import SearchResponse
from services.datasource import PartDataSource, UpstreamError
from services.deps import get_datasource

router = APIRouter(prefix="/api")

_STATUS = {"timeout": 504, "unavailable": 502}


@router.get("/search", response_model=SearchResponse)
async def search(
    q: str = "",
    page: int = Query(1, ge=1),
    ds: PartDataSource = Depends(get_datasource),
) -> SearchResponse:
    try:
        results = await ds.search(q, page)
    except UpstreamError as exc:
        raise HTTPException(status_code=_STATUS[exc.kind], detail=str(exc)) from exc
    return SearchResponse(page=page, results=results)
