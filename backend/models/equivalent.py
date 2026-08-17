"""Response models for GET /api/equivalent/<mpn_key> (spec §9)."""

from datetime import datetime

from pydantic import BaseModel


class OriginalRef(BaseModel):
    mpn_key: str
    mpn: str
    package: str
    price_usd: float | None
    stock: int
    # None when the part has no LCSC listing, which is also when the matcher
    # cannot run. The distributor names whose price and stock these are.
    lcsc: str | None = None
    distributor: str | None = None


class EquivalentMatch(BaseModel):
    mpn_key: str
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
