"""Response models for GET /api/part/<lcsc_code>/equivalent (spec §9)."""

from datetime import datetime

from pydantic import BaseModel


class OriginalRef(BaseModel):
    lcsc: str
    mpn: str
    package: str
    price_usd: float
    stock: int


class EquivalentMatch(BaseModel):
    lcsc: str
    mpn: str
    price_usd: float
    stock: int
    package: str
    match_reason: str
    percent_cheaper: int


class EquivalentResponse(BaseModel):
    original: OriginalRef
    equivalent: EquivalentMatch | None
    reason: str | None = None
    as_of: datetime
