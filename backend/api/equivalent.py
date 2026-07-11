"""GET /api/part/<lcsc_code>/equivalent — the matcher (spec §9/§10)."""

from fastapi import APIRouter, Depends, HTTPException

from models.equivalent import EquivalentResponse
from services.datasource import PartDataSource, UpstreamError, UPSTREAM_STATUS
from services.deps import get_datasource
from services.matcher import find_equivalent

router = APIRouter(prefix="/api")


@router.get("/part/{lcsc_code}/equivalent", response_model=EquivalentResponse)
async def get_equivalent(
    lcsc_code: str,
    ds: PartDataSource = Depends(get_datasource),
) -> EquivalentResponse:
    try:
        result = await find_equivalent(ds, lcsc_code)
    except UpstreamError as exc:
        raise HTTPException(status_code=UPSTREAM_STATUS[exc.kind], detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail=f"Part {lcsc_code} not found")
    return result
