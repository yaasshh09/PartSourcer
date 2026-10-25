"""GET /api/history/{mpn_key}: the recorded LCSC price and stock for a part.

Rows come from the nightly recorder, which reads on the same canonical path
the pages read, so a chart point and the price on screen share a basis. Only
LCSC is recorded today, and the response says so rather than letting a chart
pass for a cross-distributor history.

recording: false means this deployment keeps no history at all, which the
page must not confuse with a part that simply has no rows yet.
"""

from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from urllib.parse import quote
from xml.sax.saxutils import escape as xml_escape

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from api.validation import check_key_length
from config import settings
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


FEED_DAYS = 365
FEED_ITEMS = 20


def _money(p: float) -> str:
    return f"${p:.4f}" if p < 0.01 else f"${p:.2f}"


def _events(key: str, rows: list) -> list[tuple[str, object]]:
    """(title, row) for the readings worth an item, oldest first."""
    if not rows:
        return []
    first = rows[0]
    out = [(f"{key} first reading: {_money(first.price_usd)}, {first.stock:,} in stock at LCSC", first)]
    for prev, cur in zip(rows, rows[1:]):
        # Compared as printed, so float noise never posts "$0.0021 to $0.0021".
        was, now = _money(prev.price_usd), _money(cur.price_usd)
        if was != now:
            out.append((f"{key} price went from {was} to {now} at LCSC", cur))
        if prev.in_stock and not cur.in_stock:
            out.append((f"{key} out of stock at LCSC", cur))
        elif cur.in_stock and not prev.in_stock:
            out.append((f"{key} back in stock: {cur.stock:,} at LCSC", cur))
    return out


@router.get("/feed/{mpn_key:path}")
async def feed(mpn_key: str, store: HistoryStore | None = Depends(get_history_store)):
    """RSS of price moves and stock flips, for people wiring up their own alerts."""
    raw = mpn_key.strip()
    check_key_length(raw)
    key = normalize_exact(raw)
    if store is None:
        raise HTTPException(status_code=404, detail="This deployment records no history")
    since = datetime.now(timezone.utc) - timedelta(days=FEED_DAYS)
    try:
        rows = await store.get_history(key, since=since)
    except Exception as exc:                     # noqa: BLE001
        raise HTTPException(status_code=503,
                            detail="Price history is unavailable right now") from exc
    link = f"{settings.site_url.rstrip('/')}/part/{quote(key, safe='/')}"
    items = "".join(
        f"<item><title>{xml_escape(title)}</title><link>{xml_escape(link)}</link>"
        f'<guid isPermaLink="false">{xml_escape(key)}@{r.recorded_at.isoformat()}</guid>'
        f"<pubDate>{format_datetime(r.recorded_at)}</pubDate></item>"
        for title, r in reversed(_events(key, rows)[-FEED_ITEMS:]))
    body = (
        '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>'
        f"<title>{xml_escape(key)} on PartSourcer</title><link>{xml_escape(link)}</link>"
        "<description>Price moves and stock changes at LCSC, read nightly from the "
        "jlcparts snapshot, which syncs about once a day.</description>"
        f"{items}</channel></rss>")
    return Response(body, media_type="application/rss+xml",
                    headers={"Cache-Control": f"public, max-age={MAX_AGE}"})


SUGGEST_LIMIT = 8


@router.get("/suggest")
async def suggest(
    response: Response,
    q: str = Query("", max_length=64),
    store: HistoryStore | None = Depends(get_history_store),
):
    """Part numbers someone has opened here that start with what is typed.

    Only a convenience for the search box, so a missing or failing store
    gives an empty list rather than an error.
    """
    prefix = normalize_exact(q)
    found: list[str] = []
    if store is not None and len(prefix) >= 2:
        try:
            found = await store.suggest(prefix, SUGGEST_LIMIT)
        except Exception:                       # noqa: BLE001
            found = []
    response.headers["Cache-Control"] = "public, max-age=300"
    return {"suggestions": found}
