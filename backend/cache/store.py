"""SQLite cache storage (spec §7).

Dumb storage: rows in, rows out, each with its as_of fetch timestamp.
Freshness/TTL decisions live in CachingPartDataSource, not here. One
connection (WAL, check_same_thread=False) guarded by a threading.Lock;
every public method runs its sync body via asyncio.to_thread so the
event loop never blocks.
"""

import asyncio
import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime

_SCHEMA = """
CREATE TABLE IF NOT EXISTS parts (
    lcsc         TEXT PRIMARY KEY,
    specs_json   TEXT NOT NULL,
    specs_as_of  TEXT NOT NULL,
    stock        INTEGER NOT NULL,
    price_usd    REAL NOT NULL,
    stock_as_of  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS search_cache (
    query        TEXT NOT NULL,
    page         INTEGER NOT NULL,
    results_json TEXT NOT NULL,
    as_of        TEXT NOT NULL,
    PRIMARY KEY (query, page)
);
"""


@dataclass
class CachedPart:
    lcsc: str
    specs: dict          # mpn, brand, package, description, datasheet_url
    specs_as_of: datetime
    stock: int
    price_usd: float
    stock_as_of: datetime


class SqliteCacheStore:
    def __init__(self, path: str):
        self._path = path
        self._conn: sqlite3.Connection | None = None
        self._lock = threading.Lock()

    def open(self) -> None:
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    async def get_search(self, query: str, page: int) -> tuple[list[dict], datetime] | None:
        return await asyncio.to_thread(self._get_search, query, page)

    async def put_search(self, query: str, page: int,
                         results: list[dict], as_of: datetime) -> None:
        await asyncio.to_thread(self._put_search, query, page, results, as_of)

    async def get_part(self, lcsc: str) -> CachedPart | None:
        return await asyncio.to_thread(self._get_part, lcsc)

    async def upsert_part(self, lcsc: str, specs: dict, stock: int,
                          price_usd: float, specs_as_of: datetime,
                          stock_as_of: datetime) -> None:
        await asyncio.to_thread(self._upsert_part, lcsc, specs, stock,
                                price_usd, specs_as_of, stock_as_of)

    # -- sync internals (run in worker threads, serialized by the lock) --

    def _get_search(self, query: str, page: int):
        with self._lock:
            row = self._conn.execute(
                "SELECT results_json, as_of FROM search_cache"
                " WHERE query = ? AND page = ?", (query, page)).fetchone()
        if row is None:
            return None
        return json.loads(row[0]), datetime.fromisoformat(row[1])

    def _put_search(self, query, page, results, as_of):
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO search_cache"
                " (query, page, results_json, as_of) VALUES (?, ?, ?, ?)",
                (query, page, json.dumps(results), as_of.isoformat()))
            self._conn.commit()

    def _get_part(self, lcsc: str):
        with self._lock:
            row = self._conn.execute(
                "SELECT lcsc, specs_json, specs_as_of, stock, price_usd,"
                " stock_as_of FROM parts WHERE lcsc = ?", (lcsc,)).fetchone()
        if row is None:
            return None
        return CachedPart(
            lcsc=row[0], specs=json.loads(row[1]),
            specs_as_of=datetime.fromisoformat(row[2]),
            stock=row[3], price_usd=row[4],
            stock_as_of=datetime.fromisoformat(row[5]))

    def _upsert_part(self, lcsc, specs, stock, price_usd, specs_as_of, stock_as_of):
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO parts (lcsc, specs_json, specs_as_of,"
                " stock, price_usd, stock_as_of) VALUES (?, ?, ?, ?, ?, ?)",
                (lcsc, json.dumps(specs), specs_as_of.isoformat(),
                 stock, price_usd, stock_as_of.isoformat()))
            self._conn.commit()
