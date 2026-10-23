"""GET /api/fx: ECB reference rates from USD, for display only."""

from fastapi import APIRouter, Depends, HTTPException, Response

from services.deps import get_fx
from services.fx import FxRates

router = APIRouter(prefix="/api")


@router.get("/fx")
async def fx(response: Response, rates: FxRates = Depends(get_fx)):
    try:
        body = await rates.get()
    except Exception as exc:                     # noqa: BLE001
        raise HTTPException(status_code=503,
                            detail="Exchange rates are unavailable right now") from exc
    response.headers["Cache-Control"] = "public, max-age=3600"
    return body
