"""Durable history storage.

HistoryStore is the interface; InMemoryHistoryStore is the test double and
PostgresHistoryStore is the production implementation. History is
append-only: a recorded price is a fact about a moment and is never
rewritten.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass
class OfferRecord:
    mpn_key: str
    lcsc: str | None
    distributor: str
    sku: str
    price_usd: float
    stock: int
    in_stock: bool
    currency: str
    recorded_at: datetime


class HistoryStore(Protocol):
    async def add_to_watchlist(self, mpn_key: str, lcsc: str | None) -> None: ...
    async def get_watchlist(self, limit: int) -> list[tuple[str, str | None]]: ...
    async def record_offers(self, records: list[OfferRecord]) -> int: ...


class InMemoryHistoryStore:
    """Test double. Same semantics as Postgres, no durability."""

    def __init__(self) -> None:
        self.watchlist: dict[str, str | None] = {}
        self.records: list[OfferRecord] = []

    async def add_to_watchlist(self, mpn_key: str, lcsc: str | None) -> None:
        if mpn_key:
            self.watchlist[mpn_key] = lcsc

    async def get_watchlist(self, limit: int) -> list[tuple[str, str | None]]:
        return list(self.watchlist.items())[:limit]

    async def record_offers(self, records: list[OfferRecord]) -> int:
        self.records.extend(records)
        return len(records)
