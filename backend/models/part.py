"""Pydantic response model for GET /api/part/<lcsc_code> (spec §9 detail).

Distinct from models.search.SearchResult so the §9 /api/search shape never
drifts. price_breaks/stock_breakdown are typed to hold real structures once
the official LCSC API lands, but are always null in v1 (jlcsearch has no
price ladder or per-warehouse stock — honesty, §5).
"""

from datetime import datetime

from pydantic import BaseModel


class PartDetail(BaseModel):
    lcsc: str                        # "C8734"
    mpn: str                         # upstream `mfr`
    brand: str | None                # not available upstream in v1 — null
    package: str                     # the footprint identifier
    description: str                 # upstream, usually empty
    stock: int                       # single total (real)
    price_usd: float                 # single unit price (real), 4dp
    price_breaks: list[dict] | None = None    # honest gap — always null in v1
    stock_breakdown: dict | None = None        # honest gap — always null in v1
    is_basic: bool | None = None     # real upstream flag
    is_preferred: bool | None = None  # real upstream flag
    datasheet_url: str | None        # not available upstream in v1 — null
    as_of: datetime                  # real fetch time (UTC)
