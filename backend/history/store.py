"""Durable history storage.

HistoryStore is the interface; InMemoryHistoryStore is the test double and
PostgresHistoryStore is the production implementation. History is
append-only: a recorded price is a fact about a moment and is never
rewritten.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

import asyncpg


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


_PG_SCHEMA = """
CREATE TABLE IF NOT EXISTS watchlist (
    mpn_key   TEXT PRIMARY KEY,
    lcsc      TEXT,
    added_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS offer_history (
    id          BIGSERIAL PRIMARY KEY,
    mpn_key     TEXT NOT NULL,
    lcsc        TEXT,
    distributor TEXT NOT NULL,
    sku         TEXT NOT NULL,
    price_usd   DOUBLE PRECISION NOT NULL,
    stock       INTEGER NOT NULL,
    in_stock    BOOLEAN NOT NULL,
    currency    TEXT NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_offer_history_lookup
    ON offer_history (mpn_key, distributor, recorded_at DESC);
"""


class PostgresHistoryStore:
    """Durable append-only history. Neon-compatible."""

    def __init__(self, dsn: str):
        self._dsn = dsn
        self._pool: asyncpg.Pool | None = None

    async def open(self) -> None:
        self._pool = await asyncpg.create_pool(self._dsn, min_size=1, max_size=4)
        async with self._pool.acquire() as conn:
            await conn.execute(_PG_SCHEMA)

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def add_to_watchlist(self, mpn_key: str, lcsc: str | None) -> None:
        if not mpn_key or self._pool is None:
            return
        async with self._pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO watchlist (mpn_key, lcsc) VALUES ($1, $2)"
                " ON CONFLICT (mpn_key) DO UPDATE SET last_seen = now(),"
                " lcsc = COALESCE(EXCLUDED.lcsc, watchlist.lcsc)",
                mpn_key, lcsc)

    async def get_watchlist(self, limit: int) -> list[tuple[str, str | None]]:
        if self._pool is None:
            return []
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT mpn_key, lcsc FROM watchlist"
                " ORDER BY last_seen DESC LIMIT $1", limit)
        return [(r["mpn_key"], r["lcsc"]) for r in rows]

    async def record_offers(self, records: list[OfferRecord]) -> int:
        if not records or self._pool is None:
            return 0
        async with self._pool.acquire() as conn:
            await conn.executemany(
                "INSERT INTO offer_history (mpn_key, lcsc, distributor, sku,"
                " price_usd, stock, in_stock, currency, recorded_at)"
                " VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)",
                [(r.mpn_key, r.lcsc, r.distributor, r.sku, r.price_usd,
                  r.stock, r.in_stock, r.currency, r.recorded_at)
                 for r in records])
        return len(records)
