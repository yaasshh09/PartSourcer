"""SQLite cache storage, v2 (MPN-keyed).

Dumb storage: rows in, rows out, each with its as_of fetch timestamp.
Freshness and TTL decisions live in CachedPartService, not here. One
connection (WAL, check_same_thread=False) guarded by a threading.Lock; every
public method runs its sync body via asyncio.to_thread so the event loop
never blocks.

There is deliberately no parts table. Every distributor call returns specs,
stock, and price in the same response, so a spec never outlives the offer
that carried it, and a separate long-TTL specs row could only ever be read
after that offer expired. Serving a 30 day old brand next to a 40 minute old
price is the mixed-freshness record Part.as_of exists to prevent.
"""

import asyncio
import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime

CACHE_SCHEMA_VERSION = 2

_SCHEMA = """
CREATE TABLE IF NOT EXISTS offers (
    listing_key  TEXT NOT NULL,
    distributor  TEXT NOT NULL,
    sku          TEXT NOT NULL,
    part_key     TEXT NOT NULL,
    listing_json TEXT NOT NULL,
    as_of        TEXT NOT NULL,
    PRIMARY KEY (listing_key, distributor, sku)
);
CREATE INDEX IF NOT EXISTS offers_part_key ON offers (part_key);
CREATE INDEX IF NOT EXISTS offers_sku ON offers (distributor, sku);
CREATE TABLE IF NOT EXISTS search_cache (
    query          TEXT PRIMARY KEY,
    limit_used     INTEGER NOT NULL,
    part_keys_json TEXT NOT NULL,
    status_json    TEXT NOT NULL,
    as_of          TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS part_cache (
    mpn_key     TEXT PRIMARY KEY,
    status_json TEXT NOT NULL,
    as_of       TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS quota_state (
    distributor TEXT PRIMARY KEY,
    resets_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS schema_meta (
    version INTEGER NOT NULL
);
"""

_CACHE_TABLES = ("offers", "search_cache", "part_cache", "quota_state",
                 "schema_meta", "parts")


@dataclass
class CachedOffer:
    listing_key: str        # normalize_exact of the listing's own MPN
    distributor: str
    sku: str
    part_key: str           # where the merge put it last time; a retrieval index
    listing: dict           # the whole RawListing, via cache.serde
    as_of: datetime


@dataclass
class SearchCacheRow:
    query: str
    limit_used: int         # the per-adapter limit this fan-out asked for
    part_keys: list[str]    # ordered, the full list at that depth
    statuses: list[dict]    # per-distributor status at cache time
    as_of: datetime


@dataclass
class PartCacheRow:
    mpn_key: str
    statuses: list[dict]
    as_of: datetime


class SqliteCacheStore:
    def __init__(self, path: str):
        self._path = path
        self._conn: sqlite3.Connection | None = None
        self._lock = threading.Lock()

    def open(self) -> None:
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._migrate()
        self._conn.executescript(_SCHEMA)
        self._conn.execute("DELETE FROM schema_meta")
        self._conn.execute("INSERT INTO schema_meta (version) VALUES (?)",
                           (CACHE_SCHEMA_VERSION,))
        self._conn.commit()

    def _migrate(self) -> None:
        """Drop and rebuild on a version mismatch.

        Legitimate because no source of truth lives here: rebuilding is free
        and correct, and on Render free the file is ephemeral anyway. Postgres
        (the SP2a history series) is never touched by this path.
        """
        try:
            row = self._conn.execute("SELECT version FROM schema_meta").fetchone()
        except sqlite3.OperationalError:
            row = None
        if row is not None and row[0] == CACHE_SCHEMA_VERSION:
            return
        for table in _CACHE_TABLES:
            self._conn.execute(f"DROP TABLE IF EXISTS {table}")
        self._conn.commit()

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    async def get_search(self, query: str) -> SearchCacheRow | None:
        return await asyncio.to_thread(self._get_search, query)

    async def put_search(self, query: str, limit_used: int,
                         part_keys: list[str], statuses: list[dict],
                         as_of: datetime) -> None:
        await asyncio.to_thread(self._put_search, query, limit_used,
                                part_keys, statuses, as_of)

    async def get_part_status(self, mpn_key: str) -> PartCacheRow | None:
        return await asyncio.to_thread(self._get_part_status, mpn_key)

    async def put_part_status(self, mpn_key: str, statuses: list[dict],
                              as_of: datetime) -> None:
        await asyncio.to_thread(self._put_part_status, mpn_key, statuses, as_of)

    async def get_offers(self, part_keys: list[str]) -> list[CachedOffer]:
        return await asyncio.to_thread(self._get_offers, part_keys)

    async def put_offers(self, offers: list[CachedOffer]) -> None:
        await asyncio.to_thread(self._put_offers, offers)

    async def get_offers_by_sku(self, pairs: list[tuple[str, str]]
                                ) -> list[CachedOffer]:
        """Rows for specific (distributor, sku) pairs.

        By sku rather than part_key because the caller is asking "what do we
        already hold for this exact offer", and a row's part_key is only where
        the last merge filed it, which can move.
        """
        return await asyncio.to_thread(self._get_offers_by_sku, pairs)

    async def find_part_key_by_sku(self, distributor: str,
                                   sku: str) -> str | None:
        return await asyncio.to_thread(self._find_part_key_by_sku,
                                       distributor, sku)

    async def get_quota_markers(self) -> dict[str, datetime]:
        return await asyncio.to_thread(self._get_quota_markers)

    async def put_quota_marker(self, distributor: str,
                               resets_at: datetime) -> None:
        await asyncio.to_thread(self._put_quota_marker, distributor, resets_at)

    # -- sync internals (run in worker threads, serialized by the lock) --

    def _get_search(self, query: str):
        with self._lock:
            row = self._conn.execute(
                "SELECT query, limit_used, part_keys_json, status_json, as_of"
                " FROM search_cache WHERE query = ?", (query,)).fetchone()
        if row is None:
            return None
        return SearchCacheRow(query=row[0], limit_used=row[1],
                              part_keys=json.loads(row[2]),
                              statuses=json.loads(row[3]),
                              as_of=datetime.fromisoformat(row[4]))

    def _put_search(self, query, limit_used, part_keys, statuses, as_of):
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO search_cache"
                " (query, limit_used, part_keys_json, status_json, as_of)"
                " VALUES (?, ?, ?, ?, ?)",
                (query, limit_used, json.dumps(part_keys),
                 json.dumps(statuses), as_of.isoformat()))
            self._conn.commit()

    def _get_part_status(self, mpn_key: str):
        with self._lock:
            row = self._conn.execute(
                "SELECT mpn_key, status_json, as_of FROM part_cache"
                " WHERE mpn_key = ?", (mpn_key,)).fetchone()
        if row is None:
            return None
        return PartCacheRow(mpn_key=row[0], statuses=json.loads(row[1]),
                            as_of=datetime.fromisoformat(row[2]))

    def _put_part_status(self, mpn_key, statuses, as_of):
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO part_cache (mpn_key, status_json, as_of)"
                " VALUES (?, ?, ?)",
                (mpn_key, json.dumps(statuses), as_of.isoformat()))
            self._conn.commit()

    def _get_offers(self, part_keys: list[str]) -> list[CachedOffer]:
        if not part_keys:
            return []
        marks = ",".join("?" * len(part_keys))
        with self._lock:
            rows = self._conn.execute(
                "SELECT listing_key, distributor, sku, part_key, listing_json,"
                f" as_of FROM offers WHERE part_key IN ({marks})",
                tuple(part_keys)).fetchall()
        return [CachedOffer(listing_key=r[0], distributor=r[1], sku=r[2],
                            part_key=r[3], listing=json.loads(r[4]),
                            as_of=datetime.fromisoformat(r[5])) for r in rows]

    def _get_offers_by_sku(self, pairs: list[tuple[str, str]]
                           ) -> list[CachedOffer]:
        if not pairs:
            return []
        # Chunked because one search can ask about every listing it just
        # fetched, and a deeper FETCH_DEPTH would otherwise walk into
        # SQLite's bound-parameter ceiling.
        out: list[CachedOffer] = []
        chunk = 200
        with self._lock:
            for i in range(0, len(pairs), chunk):
                batch = pairs[i:i + chunk]
                clause = " OR ".join(
                    ["(distributor = ? AND sku = ?)"] * len(batch))
                params = tuple(x for pair in batch for x in pair)
                out.extend(self._conn.execute(
                    "SELECT listing_key, distributor, sku, part_key,"
                    f" listing_json, as_of FROM offers WHERE {clause}",
                    params).fetchall())
        return [CachedOffer(listing_key=r[0], distributor=r[1], sku=r[2],
                            part_key=r[3], listing=json.loads(r[4]),
                            as_of=datetime.fromisoformat(r[5])) for r in out]

    def _put_offers(self, offers: list[CachedOffer]) -> None:
        if not offers:
            return
        with self._lock:
            self._conn.executemany(
                "INSERT OR REPLACE INTO offers (listing_key, distributor, sku,"
                " part_key, listing_json, as_of) VALUES (?, ?, ?, ?, ?, ?)",
                [(o.listing_key, o.distributor, o.sku, o.part_key,
                  json.dumps(o.listing), o.as_of.isoformat()) for o in offers])
            self._conn.commit()

    def _find_part_key_by_sku(self, distributor: str, sku: str) -> str | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT part_key FROM offers WHERE distributor = ? AND sku = ?",
                (distributor, sku)).fetchone()
        return row[0] if row is not None else None

    def _get_quota_markers(self) -> dict[str, datetime]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT distributor, resets_at FROM quota_state").fetchall()
        return {r[0]: datetime.fromisoformat(r[1]) for r in rows}

    def _put_quota_marker(self, distributor: str, resets_at: datetime) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO quota_state (distributor, resets_at)"
                " VALUES (?, ?)", (distributor, resets_at.isoformat()))
            self._conn.commit()
