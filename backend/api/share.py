"""Link previews for a part: a PNG card and a page that carries it.

GET /api/og/part/{mpn_key} draws the card a chat app or social site shows
when a part link is pasted. GET /api/share/part/{mpn_key} is the link to
paste: it holds the Open Graph tags that point at the card and sends a person
straight on to the part page, so previews work without the static site
having to render anything on a server.

Same rules as the README badge. The card reads the cached part the page
reads, prints when its numbers were read because previews are cached for a
long time, names the distributor behind the price instead of calling it the
cheapest, and answers every failure with an image rather than a broken one.
"""

import io
from html import escape
from urllib.parse import quote

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse, Response
from PIL import Image, ImageDraw, ImageFont

from api.legacy import LEGACY_CODE, canonical_mpn
from api.validation import MAX_KEY_LEN
from cache.cached_part_service import CachedPartService
from config import settings
from models.offer import Offer, Part
from services.adapters.lcsc import LcscAdapter
from services.datasource import UpstreamError
from services.deps import get_cached_service, get_lcsc_adapter
from services.matching import normalize_exact
from services.part_service import ALL_DISTRIBUTORS

router = APIRouter(prefix="/api")

LABEL = {"lcsc": "LCSC", "mouser": "Mouser", "digikey": "DigiKey"}
OK_MAX_AGE = 3600       # the offer cache TTL; a card is no fresher than its row
ERR_MAX_AGE = 300
YELLOW, INK, SUB, ORANGE = "#ffe14d", "#111111", "#4a4838", "#ff5c38"
W, H = 1200, 630


def headline(part: Part) -> Offer | None:
    """The one offer the part page shows as the price (offers.js headlineOffer)."""
    if not part.offers:
        return None
    if part.cheapest:
        for o in part.offers:
            if o.distributor == part.cheapest.distributor and o.sku == part.cheapest.sku:
                return o
    comparable = [o for o in part.offers
                  if o.match_tier == "exact" and o.in_stock and o.currency == "USD"]
    rank = {d: i for i, d in enumerate(ALL_DISTRIBUTORS)}
    return min(comparable or part.offers, key=lambda o: (
        not o.in_stock, float("inf") if o.price_usd is None else o.price_usd,
        rank.get(o.distributor, len(rank))))


def _money(p: float) -> str:
    return f"${p:.4f}" if p < 0.01 else f"${p:.2f}"


def summary(part: Part) -> list[str]:
    """Price, stock and read time, as the card prints them."""
    h = headline(part)
    lines = []
    if h is not None:
        price = "no price" if h.price_usd is None else _money(h.price_usd)
        lines.append(f"{price} at {LABEL.get(h.distributor, h.distributor)}")
    stock = sum(o.stock for o in part.offers
                if o.match_tier == "exact" and o.in_stock and o.stock > 0)
    lines.append(f"{stock:,} in stock across distributors" if stock else "out of stock")
    if part.as_of:
        d = part.as_of
        lines.append(f"Read {d:%b} {d.day}, {d.year} · {d:%H:%M} UTC. Excludes shipping and tax.")
    return lines


def _font(size: int):
    return ImageFont.load_default(size=size)


def _fit(draw, text: str, size: int, width: int):
    """The largest font up to size that keeps the text inside width."""
    while size > 20 and draw.textlength(text, font=_font(size)) > width:
        size -= 4
    return _font(size)


def _card(title: str, subtitle: str, lines: list[str]) -> bytes:
    img = Image.new("RGB", (W, H), YELLOW)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W - 1, H - 1], outline=INK, width=14)
    d.rectangle([60, 56, 92, 88], fill=INK)
    d.rectangle([70, 66, 82, 78], fill=ORANGE)
    d.text((110, 52), "PARTSOURCER", font=_font(36), fill=INK)
    d.text((60, 150), title, font=_fit(d, title, 96, W - 120), fill=INK)
    if subtitle:
        d.text((60, 270), subtitle, font=_fit(d, subtitle, 36, W - 120), fill=SUB)
    y = 350
    for i, line in enumerate(lines):
        size = 56 if i == 0 else 34
        d.text((60, y), line, font=_fit(d, line, size, W - 120), fill=INK)
        y += size + 22
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


async def _part(raw: str, cached: CachedPartService, lcsc: LcscAdapter) -> Part | None:
    raw = raw.strip()
    if not raw or len(raw) > MAX_KEY_LEN:
        return None
    key = raw
    if LEGACY_CODE.fullmatch(raw):
        key = await canonical_mpn(raw, cached, lcsc) or raw
    try:
        part, _, _ = await cached.lookup(normalize_exact(key))
    except UpstreamError:
        return None
    return part


def _subtitle(part: Part) -> str:
    return " · ".join(x for x in (part.brand, part.package, part.description) if x)


@router.get("/og/part/{mpn_key:path}")
async def og_card(mpn_key: str,
                  cached: CachedPartService = Depends(get_cached_service),
                  lcsc: LcscAdapter = Depends(get_lcsc_adapter)):
    part = await _part(mpn_key, cached, lcsc)
    if part is None:
        body = _card("Find the cheapest in-stock part",
                     "Stock and price across LCSC, Mouser and DigiKey", [])
        age = ERR_MAX_AGE
    else:
        body, age = _card(part.mpn, _subtitle(part), summary(part)), OK_MAX_AGE
    return Response(body, media_type="image/png",
                    headers={"Cache-Control": f"public, max-age={age}"})


@router.get("/share/part/{mpn_key:path}", response_class=HTMLResponse)
async def share_page(mpn_key: str,
                     cached: CachedPartService = Depends(get_cached_service),
                     lcsc: LcscAdapter = Depends(get_lcsc_adapter)):
    part = await _part(mpn_key, cached, lcsc)
    site = settings.site_url.rstrip("/")
    key = part.mpn_key if part else normalize_exact(mpn_key)[:MAX_KEY_LEN]
    path = quote(key, safe="/")
    page_url, image_url = f"{site}/part/{path}", f"{site}/api/og/part/{path}"
    title = f"{part.mpn} · PartSourcer" if part else "PartSourcer"
    desc = (" ".join(summary(part)) if part else
            "Stock and price across LCSC, Mouser and DigiKey, each stamped with when it was read.")
    t, ds, pu, iu = escape(title), escape(desc), escape(page_url), escape(image_url)
    html = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f'<title>{t}</title><meta name="description" content="{ds}">'
        f'<meta property="og:type" content="website"><meta property="og:title" content="{t}">'
        f'<meta property="og:description" content="{ds}">'
        f'<meta property="og:url" content="{pu}">'
        f'<meta property="og:image" content="{iu}">'
        '<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">'
        '<meta name="twitter:card" content="summary_large_image">'
        f'<link rel="canonical" href="{pu}">'
        f'<meta http-equiv="refresh" content="0; url={pu}">'
        f'</head><body><a href="{pu}">{t}</a></body></html>'
    )
    age = OK_MAX_AGE if part else ERR_MAX_AGE
    return HTMLResponse(html, headers={"Cache-Control": f"public, max-age={age}"})
