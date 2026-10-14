"""GET /api/history/{mpn_key}: the recorded LCSC price and stock for a part.

Rows come from the nightly recorder, which reads on the same canonical path
the pages read, so a chart point and the price on screen share a basis. Only
LCSC is recorded today, and the response says so rather than letting a chart
pass for a cross-distributor history.

recording: false means this deployment keeps no history at all, which the
page must not confuse with a part that simply has no rows yet.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from api.validation import check_key_length
from history.store import HistoryStore
from services.deps import get_history_store
from services.matching import normalize_exact

router = APIRouter(prefix="/api")

MAX_AGE = 3600   # rows land once a night; an hour is plenty fresh
TREND_DAYS = 7
MIN_SPAN = timedelta(days=2)   # two readings an hour apart are not a week
MAX_KEYS = 50                  # a search page is 20 results; leave slack


@router.get("/history/{mpn_key:path}")
async def history(
    mpn_key: str,
    response: Response,
    days: int = Query(90, ge=1, le=365),
    store: HistoryStore | None = Depends(get_history_store),
):
    raw = mpn_key.strip()
    check_key_length(raw)
    key = normalize_exact(raw)
    body = {"mpn_key": key, "distributor": "lcsc", "recording": store is not None,
            "points": []}
    if store is not None:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        try:
            rows = await store.get_history(key, since=since)
        except Exception as exc:                 # noqa: BLE001
            # An empty chart would read as "nothing recorded", which is a
            # claim we cannot make while the store is unreachable.
            raise HTTPException(status_code=503,
                                detail="Price history is unavailable right now") from exc
        body["points"] = [{"at": r.recorded_at.isoformat(), "price_usd": r.price_usd,
                           "stock": r.stock} for r in rows]
    response.headers["Cache-Control"] = f"public, max-age={MAX_AGE}"
    return body


def _pct(first: float, last: float) -> int | None:
    return None if first <= 0 else round((last - first) / first * 100)


@router.get("/trends")
async def trends(
    response: Response,
    keys: list[str] = Query(..., min_length=1, max_length=MAX_KEYS),
    store: HistoryStore | None = Depends(get_history_store),
):
    """First-to-last change over the past week, per part, for search cards.

    A part is left out unless it has two readings at least MIN_SPAN apart,
    so a badge never calls one night's wobble a weekly trend.
    """
    norm = {normalize_exact(k.strip()) for k in keys}
    for k in norm:
        check_key_length(k)
    body = {"recording": store is not None, "days": TREND_DAYS, "trends": {}}
    if store is not None:
        since = datetime.now(timezone.utc) - timedelta(days=TREND_DAYS)
        try:
            rows = await store.get_history_many(sorted(norm), since=since)
        except Exception as exc:                 # noqa: BLE001
            raise HTTPException(status_code=503,
                                detail="Price history is unavailable right now") from exc
        by_key: dict[str, list] = {}
        for r in rows:
            by_key.setdefault(r.mpn_key, []).append(r)
        for key, rs in by_key.items():
            first, last = rs[0], rs[-1]
            if last.recorded_at - first.recorded_at < MIN_SPAN:
                continue
            body["trends"][key] = {
                "price_pct": _pct(first.price_usd, last.price_usd),
                "stock_pct": _pct(first.stock, last.stock),
                "from": first.recorded_at.isoformat(),
                "to": last.recorded_at.isoformat()}
    response.headers["Cache-Control"] = f"public, max-age={MAX_AGE}"
    return body
