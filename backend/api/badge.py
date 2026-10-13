"""GET /api/badge/{mpn_key}: a stock badge for a project README.

Reads the same cached part the detail page reads, so a badge never shows a
number the site would not. Every state answers 200 with an SVG, since a
README renders anything else as a broken image, and the read date is always
drawn on it, since the image proxy in front of a README caches it.

Price appears only when the part service made a gated cheapest claim.
Picking one offer's price here would be a cheapest claim made without the
gates.
"""

from html import escape

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from api.legacy import LEGACY_CODE, canonical_mpn
from api.part import missing_part
from api.validation import check_key_length
from cache.cached_part_service import CachedPartService
from services.adapters.lcsc import LcscAdapter
from services.datasource import UpstreamError
from services.deps import get_cached_service, get_lcsc_adapter
from services.matching import normalize_exact

router = APIRouter(prefix="/api")

LABEL = "PartSourcer"
GREEN, GREY, INK = "#1d7a45", "#8a8778", "#111"
CHAR_PX = 7          # rough Verdana 11px advance; a little slack beats clipping
OK_MAX_AGE = 3600    # the stock and price cache TTL, so no fresher than the row
ERR_MAX_AGE = 300


def _svg(value: str, color: str) -> str:
    lw, vw = len(LABEL) * CHAR_PX + 12, len(value) * CHAR_PX + 12
    w = lw + vw
    label, value = escape(LABEL), escape(value)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="20" role="img" '
        f'aria-label="{label}: {value}"><title>{label}: {value}</title>'
        f'<rect width="{lw}" height="20" fill="{INK}"/>'
        f'<rect x="{lw}" width="{vw}" height="20" fill="{color}"/>'
        f'<g fill="#fff" font-family="Verdana,DejaVu Sans,sans-serif" font-size="11">'
        f'<text x="6" y="14">{label}</text><text x="{lw + 6}" y="14">{value}</text></g></svg>'
    )


def _badge(value: str, color: str, max_age: int) -> Response:
    return Response(_svg(value, color), media_type="image/svg+xml",
                    headers={"Cache-Control": f"public, max-age={max_age}"})


@router.get("/badge/{mpn_key:path}")
async def badge(
    mpn_key: str,
    cached: CachedPartService = Depends(get_cached_service),
    lcsc: LcscAdapter = Depends(get_lcsc_adapter),
):
    raw = mpn_key.strip()
    check_key_length(raw)
    key = raw
    if LEGACY_CODE.fullmatch(raw):
        key = await canonical_mpn(raw, cached, lcsc) or raw
    try:
        part, sources, _ = await cached.lookup(normalize_exact(key))
    except UpstreamError:
        return _badge("unavailable", GREY, ERR_MAX_AGE)
    if part is None:
        # Not found only when every distributor answered; otherwise we do
        # not know, which is a different thing to print.
        exc: HTTPException = missing_part(raw, sources)
        return _badge("not found" if exc.status_code == 404 else "unavailable",
                      GREY, OK_MAX_AGE if exc.status_code == 404 else ERR_MAX_AGE)

    # Exact matches only: a reel under a variant part number is a different
    # thing to order. Same rule as the part page's stock total.
    stock = sum(o.stock for o in part.offers
                if o.match_tier == "exact" and o.in_stock and o.stock > 0)
    when = part.as_of.strftime("%b %d").replace(" 0", " ") if part.as_of else "date unknown"
    if not stock:
        return _badge(f"out of stock · {when}", GREY, OK_MAX_AGE)
    price = f" · from ${part.cheapest.price_usd:.2f}" if part.cheapest else ""
    if part.cheapest and part.cheapest.price_usd < 0.01:
        price = f" · from ${part.cheapest.price_usd:.4f}"
    return _badge(f"{stock:,} in stock{price} · {when}", GREEN, OK_MAX_AGE)
