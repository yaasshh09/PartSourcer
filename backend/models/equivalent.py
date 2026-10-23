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


class SpecCheck(BaseModel):
    """One gate the matcher ran, with both sides as a person would write them.

    original is None when the original part lists no value, which is also
    when the gate did not run; rule then says so instead of claiming a pass.
    """
    spec: str
    original: str | None
    candidate: str | None
    rule: str


class EquivalentMatch(BaseModel):
    mpn_key: str
    lcsc: str
    mpn: str
    price_usd: float
    stock: int
    package: str
    match_reason: str
    percent_cheaper: int
    checks: list[SpecCheck] = []


class EquivalentResponse(BaseModel):
    original: OriginalRef
    equivalent: EquivalentMatch | None
    # Runners-up to `equivalent`, cheapest first, each verified on the same
    # gates. Never repeats `equivalent`, and always empty when it is None.
    alternatives: list[EquivalentMatch] = []
    # A part that beats the original on at least one checked spec, is no
    # worse on any, and costs no more. Independent of `equivalent`: it can be
    # set when nothing is cheaper, and never repeats a listed swap.
    upgrade: EquivalentMatch | None = None
    reason: str | None = None
    as_of: datetime
