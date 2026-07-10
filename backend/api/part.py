"""GET /api/part/<lcsc_code> — spec §9 detail."""

from fastapi import APIRouter, Depends, HTTPException

from models.part import PartDetail
from services.datasource import PartDataSource, UpstreamError
from services.deps import get_datasource

router = APIRouter(prefix="/api")

_STATUS = {"timeout": 504, "unavailable": 502}


@router.get("/part/{lcsc_code}", response_model=PartDetail)
async def get_part(
    lcsc_code: str,
    refresh: bool = False,
    ds: PartDataSource = Depends(get_datasource),
) -> PartDetail:
    try:
        detail = await ds.get_part(lcsc_code, refresh=refresh)
    except UpstreamError as exc:
        raise HTTPException(status_code=_STATUS[exc.kind], detail=str(exc)) from exc
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Part {lcsc_code} not found")
    return detail
