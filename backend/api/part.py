"""GET /api/part/{mpn_key}: the multi-distributor detail surface.

Real MPNs contain slashes (LM358P/NOPB), so the path converter has to be
greedy, which means the legacy LCSC routes cannot be separate registrations:
Starlette has no regex path converter and FastAPI does not fall through from
a matched route. One handler disambiguates instead.
"""

import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse

from api.legacy import LEGACY_CODE, canonical_mpn
from api.validation import check_key_length
from cache.cached_part_service import CachedPartService
from models.offer import PartResponse
from services.adapters.lcsc import LcscAdapter
from services.datasource import UPSTREAM_STATUS, UpstreamError
from services.deps import get_cached_service, get_history_store, get_lcsc_adapter
from services.matching import normalize_exact

router = APIRouter(prefix="/api")

_LEGACY_EQUIVALENT = re.compile(r"(C\d+)/equivalent")


def missing_part(raw: str, sources) -> HTTPException:
    """Why no part came back, told honestly.

    Not found is a claim that every distributor was asked and none has it.
    With one of them timed out or down we only know that the others do not,
    so that is an upstream failure, not a 404. disabled never counts: it was
    never asked and never will be. Only names and states go in the detail,
    never a source's own message.
    """
    unasked = [s for s in sources if s.state not in ("ok", "disabled")]
    if not unasked:
        return HTTPException(status_code=404, detail=f"Part {raw} not found")
    code = 504 if any(s.state == "timeout" for s in unasked) else 502
    names = ", ".join(f"{s.distributor} {s.state}" for s in unasked)
    return HTTPException(status_code=code,
                         detail=f"Could not check every distributor for {raw} ({names})")


@router.get("/part/{mpn_key:path}", response_model=PartResponse)
async def get_part(
    mpn_key: str,
    refresh: bool = False,
    cached: CachedPartService = Depends(get_cached_service),
    lcsc: LcscAdapter = Depends(get_lcsc_adapter),
):
    raw = mpn_key.strip()
    check_key_length(raw)

    # 2SC1815 is widely catalogued as C1815, so a code-shaped string is not
    # proof of a SKU. Resolve first, and fall through to MPN handling when it
    # does not resolve, rather than 404ing a real part.
    legacy = _LEGACY_EQUIVALENT.fullmatch(raw)
    if legacy is not None:
        canonical = await canonical_mpn(legacy.group(1), cached, lcsc)
        if canonical is not None:
            return RedirectResponse(f"/api/equivalent/{canonical}",
                                    status_code=302)
        raise HTTPException(status_code=404, detail=f"Part {raw} not found")

    if LEGACY_CODE.fullmatch(raw):
        canonical = await canonical_mpn(raw, cached, lcsc)
        if canonical is not None:
            return RedirectResponse(f"/api/part/{canonical}", status_code=302)

    key = normalize_exact(raw)
    try:
        part, sources, canonical_key = await cached.lookup(key, refresh=refresh)
    except UpstreamError as exc:
        raise HTTPException(status_code=UPSTREAM_STATUS[exc.kind],
                            detail=str(exc)) from exc
    if part is None:
        raise missing_part(raw, sources)
    if not canonical_key:
        # The request named a key that folds into another part. Redirect so
        # the address bar carries the name the merge actually uses.
        return RedirectResponse(f"/api/part/{part.mpn_key}", status_code=302)

    # A part someone looked at is a part worth tracking. Never fatal: the
    # detail response must not depend on the history store being reachable.
    store = get_history_store()
    if store is not None:
        lcsc_offer = next((o for o in part.offers if o.distributor == "lcsc"),
                          None)
        if lcsc_offer is not None:
            try:
                await store.add_to_watchlist(part.mpn_key, lcsc_offer.sku)
            except Exception:                   # noqa: BLE001
                pass

    return PartResponse(part=part, sources=sources)
