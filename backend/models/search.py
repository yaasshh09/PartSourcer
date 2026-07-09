"""Pydantic response models for /api/search (spec §9 shapes)."""

from datetime import datetime

from pydantic import BaseModel


class SearchResult(BaseModel):
    lcsc: str                  # "C8734" — upstream int, C-prefixed by the datasource
    mpn: str                   # upstream `mfr` (it IS the part number)
    brand: str | None          # not available upstream in v1 — always null
    package: str
    description: str           # upstream usually empty
    stock: int
    price_usd: float           # assumed USD, rounded to 4dp
    datasheet_url: str | None  # not available upstream in v1 — always null
    as_of: datetime            # real fetch time (UTC)


class SearchResponse(BaseModel):
    page: int
    results: list[SearchResult]
