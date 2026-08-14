"""GET /api/equivalent/{mpn_key}: the matcher, reached by canonical MPN.

Moved out from under /part because real MPNs contain slashes, so a greedy
path converter on /part would swallow /equivalent as part of the identifier.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse

from cache.cached_part_service import CachedPartService
from models.equivalent import EquivalentResponse, OriginalRef
from models.offer import Part
from services.datasource import UPSTREAM_STATUS, UpstreamError
from services.deps import get_cached_service, get_matcher_source
from services.lcsc_matcher_source import LcscMatcherSource
from services.matcher import find_equivalent
from services.matching import normalize_exact

router = APIRouter(prefix="/api")

NO_LCSC_REASON = ("This part has no LCSC listing, and v1 equivalent matching "
                  "uses LCSC parametric data only, so no drop-in can be "
                  "verified for it.")


def _no_lcsc_response(part: Part) -> EquivalentResponse:
    """An honest null built from a real offer, never a fabricated original."""
    best = min(part.offers, key=lambda o: (not o.in_stock, o.price_usd))
    return EquivalentResponse(
        original=OriginalRef(mpn_key=part.mpn_key, mpn=part.mpn,
                             package=part.package, price_usd=best.price_usd,
                             stock=best.stock, lcsc=None,
                             distributor=best.distributor),
        equivalent=None, reason=NO_LCSC_REASON,
        as_of=datetime.now(timezone.utc))


@router.get("/equivalent/{mpn_key:path}", response_model=EquivalentResponse)
async def get_equivalent(
    mpn_key: str,
    cached: CachedPartService = Depends(get_cached_service),
    source: LcscMatcherSource = Depends(get_matcher_source),
):
    key = normalize_exact(mpn_key)
    try:
        part, _sources, canonical = await cached.lookup(key)
    except UpstreamError as exc:
        raise HTTPException(status_code=UPSTREAM_STATUS[exc.kind],
                            detail=str(exc)) from exc
    if part is None or not part.offers:
        raise HTTPException(status_code=404, detail=f"Part {mpn_key} not found")
    if not canonical:
        return RedirectResponse(f"/api/equivalent/{part.mpn_key}",
                                status_code=302)

    lcsc_offer = next((o for o in part.offers
                       if o.distributor == "lcsc" and o.match_tier == "exact"),
                      None)
    if lcsc_offer is None:
        return _no_lcsc_response(part)

    try:
        result = await find_equivalent(source, lcsc_offer.sku)
    except UpstreamError as exc:
        raise HTTPException(status_code=UPSTREAM_STATUS[exc.kind],
                            detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail=f"Part {mpn_key} not found")
    return result
