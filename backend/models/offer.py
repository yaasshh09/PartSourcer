"""Multi-distributor response shapes (SP1).

A part is a canonical MPN. Every distributor listing is an Offer hanging
off it. Honesty rules that live in this module: Part.as_of is the OLDEST
contributing offer, never the newest, and a cheapest claim always carries
the basis it was computed on.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, computed_field

Distributor = Literal["lcsc", "mouser", "digikey"]
MatchTier = Literal["exact", "packaging"]
SourceState = Literal["ok", "timeout", "unavailable", "quota_exhausted", "disabled"]


class Offer(BaseModel):
    distributor: Distributor
    sku: str
    mpn_as_listed: str          # verbatim, so a user can audit the match
    match_tier: MatchTier
    match_note: str | None      # set only when match_tier == "packaging"
    stock: int
    in_stock: bool
    price_usd: float            # unit price at quantity 1
    price_breaks: list[dict] | None   # real for mouser/digikey, null for lcsc
    currency: str
    product_url: str | None
    as_of: datetime


class Cheapest(BaseModel):
    distributor: Distributor
    sku: str
    price_usd: float
    compared_sources: int       # how many sources actually answered
    of_sources: int             # how many were asked


class DistributorStatus(BaseModel):
    distributor: Distributor
    state: SourceState
    detail: str | None
    as_of: datetime | None


class Part(BaseModel):
    mpn_key: str
    mpn: str
    brand: str | None
    package: str
    description: str
    datasheet_url: str | None
    offers: list[Offer]
    cheapest: Cheapest | None
    cheapest_unavailable_reason: str | None

    @computed_field
    @property
    def as_of(self) -> datetime | None:
        """Oldest offer. A fast distributor must never make the record look
        fresher than its stalest component."""
        if not self.offers:
            return None
        return min(o.as_of for o in self.offers)


class SearchResponseV2(BaseModel):
    page: int
    query: str
    results: list[Part]
    sources: list[DistributorStatus]
