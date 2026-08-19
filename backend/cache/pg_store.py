"""Postgres cache storage, the same contract as SqliteCacheStore.

SQLite is one file guarded by one lock, which is exactly right for a single
always-on process and exactly wrong for anything that runs as several. Two
instances each get their own file, so the same part can carry two different
prices at once and each instance counts its own upstream calls. Both of those
are things this project promises not to do, so anywhere the app runs more than
once it reads and writes here instead.

Storage stays dumb: rows in, rows out, each with its as_of. Freshness and TTL
decisions live in CachedPartService, exactly as they do for SQLite.

Tables are prefixed cache_ because this database also holds the SP2a history
series, which is a source of truth and must never be caught by a cache
rebuild. The prefix makes the rebuild's blast radius something you can read off
the name. JSON is stored as TEXT rather than JSONB for the same reason it is in
SQLite: nothing ever queries inside it, and matching the two implementations
row for row is worth more here than a column type nobody reads.
"""

import json
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime

import asyncpg

log = logging.getLogger("partsourcer.pg")

from cache.store import (CACHE_SCHEMA_VERSION, CachedOffer, PartCacheRow,
                         SearchCacheRow)

# Any bigint works; it only has to be the same in every process. Two cold
# starts landing together would otherwise race to drop and recreate the same
# tables, and the loser would query a table that no longer exists.
_MIGRATION_LOCK = 728401553

_TABLES = ("cache_offers", "cache_search", "cache_part", "cache_parametric",
           "cache_quota_state", "cache_schema_meta")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cache_offers (
    listing_key  TEXT NOT NULL,
    distributor  TEXT NOT NULL,
    sku          TEXT NOT NULL,
    part_key     TEXT NOT NULL,
    listing_json TEXT NOT NULL,
    as_of        TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (listing_key, distributor, sku)
);
CREATE INDEX IF NOT EXISTS cache_offers_part_key ON cache_offers (part_key);
CREATE INDEX IF NOT EXISTS cache_offers_sku ON cache_offers (distributor, sku);
CREATE TABLE IF NOT EXISTS cache_search (
    query          TEXT PRIMARY KEY,
    limit_used     INTEGER NOT NULL,
    part_keys_json TEXT NOT NULL,
    status_json    TEXT NOT NULL,
    as_of          TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS cache_part (
    mpn_key     TEXT PRIMARY KEY,
    status_json TEXT NOT NULL,
    as_of       TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS cache_parametric (
    key       TEXT PRIMARY KEY,
    rows_json TEXT NOT NULL,
    as_of     TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS cache_quota_state (
    distributor TEXT PRIMARY KEY,
    resets_at   TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS cache_schema_meta (
    version INTEGER NOT NULL
);
"""

_PRUNABLE = ("cache_offers", "cache_search", "cache_part", "cache_parametric")


def _deleted(status: str) -> int:
    """asyncpg reports a delete as the string DELETE followed by a count."""
    try:
        return int(status.rsplit(" ", 1)[1])
    except (IndexError, ValueError):
        return 0


class PostgresCacheStore:
    """Shared cache. Neon compatible, safe to run from many instances."""

    def __init__(self, dsn: str):
        self._dsn = dsn
        self._pool: asyncpg.Pool | None = None

    async def open(self) -> None:
        # statement_cache_size=0 because the Neon pooled endpoint is PgBouncer
        # in transaction mode, where a prepared statement from one checkout is
        # not there on the next and the asyncpg cache would ask for it anyway.
        t0 = time.perf_counter()
        self._pool = await asyncpg.create_pool(
            self._dsn, min_size=1, max_size=4, statement_cache_size=0)
        t1 = time.perf_counter()
        async with self._pool.acquire() as conn:
            await self._migrate(conn)
        # TEMPORARY, alongside _timed. If this line shows up once per request
        # then the lifespan is restarting and the pool never gets reused.
        log.info("pg pool opened create=%.0fms migrate=%.0fms",
                 (t1 - t0) * 1000, (time.perf_counter() - t1) * 1000)

    @staticmethod
    async def _schema_version(conn) -> int | None:
        """The version stamped in the database, or None before there is one."""
        try:
            return await conn.fetchval(
                "SELECT version FROM cache_schema_meta LIMIT 1")
        except asyncpg.UndefinedTableError:
            return None

    async def _migrate(self, conn) -> None:
        """Rebuild on a version mismatch, exactly as the SQLite store does.

        Read the stamped version first and leave if it already matches. Every
        cold start runs this and the usual answer is that there is nothing to
        do, so the common path costs one query instead of a lock plus a dozen
        DDL statements against a database that may be a continent away.

        Rebuilding is free and correct because no source of truth lives in
        these tables. The advisory lock makes it safe when several instances
        start at once, and only cache_ tables are ever dropped, so the history
        series that shares this database is never in scope.
        """
        if await self._schema_version(conn) == CACHE_SCHEMA_VERSION:
            return
        await conn.execute("SELECT pg_advisory_lock($1)", _MIGRATION_LOCK)
        try:
            # Read again now that we hold the lock. Another instance may have
            # rebuilt the whole thing while we queued behind it, and dropping
            # its fresh tables would be pure waste.
            if await self._schema_version(conn) == CACHE_SCHEMA_VERSION:
                return
            for table in _TABLES:
                await conn.execute(f"DROP TABLE IF EXISTS {table}")
            await conn.execute(_SCHEMA)
            await conn.execute("DELETE FROM cache_schema_meta")
            await conn.execute(
                "INSERT INTO cache_schema_meta (version) VALUES ($1)",
                CACHE_SCHEMA_VERSION)
        finally:
            await conn.execute("SELECT pg_advisory_unlock($1)", _MIGRATION_LOCK)

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    @asynccontextmanager
    async def _timed(self, label: str):
        """TEMPORARY. Splits waiting for a connection from running the query.

        A cached read costs about 750ms per query in production against a
        database roughly 60ms away, which is far too much for either half on
        its own. This says which half it is. Remove once that is answered.
        """
        t0 = time.perf_counter()
        async with self._pool.acquire() as conn:
            t1 = time.perf_counter()
            try:
                yield conn
            finally:
                t2 = time.perf_counter()
                log.info("pg %s acquire=%.0fms query=%.0fms size=%d idle=%d",
                         label, (t1 - t0) * 1000, (t2 - t1) * 1000,
                         self._pool.get_size(), self._pool.get_idle_size())

    async def get_search(self, query: str) -> SearchCacheRow | None:
        async with self._timed("get_search") as conn:
            row = await conn.fetchrow(
                "SELECT query, limit_used, part_keys_json, status_json, as_of"
                " FROM cache_search WHERE query = $1", query)
        if row is None:
            return None
        return SearchCacheRow(query=row["query"], limit_used=row["limit_used"],
                              part_keys=json.loads(row["part_keys_json"]),
                              statuses=json.loads(row["status_json"]),
                              as_of=row["as_of"])

    async def put_search(self, query: str, limit_used: int,
                         part_keys: list[str], statuses: list[dict],
                         as_of: datetime) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO cache_search (query, limit_used, part_keys_json,"
                " status_json, as_of) VALUES ($1, $2, $3, $4, $5)"
                " ON CONFLICT (query) DO UPDATE SET"
                " limit_used = EXCLUDED.limit_used,"
                " part_keys_json = EXCLUDED.part_keys_json,"
                " status_json = EXCLUDED.status_json, as_of = EXCLUDED.as_of",
                query, limit_used, json.dumps(part_keys),
                json.dumps(statuses), as_of)

    async def get_part_status(self, mpn_key: str) -> PartCacheRow | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT mpn_key, status_json, as_of FROM cache_part"
                " WHERE mpn_key = $1", mpn_key)
        if row is None:
            return None
        return PartCacheRow(mpn_key=row["mpn_key"],
                            statuses=json.loads(row["status_json"]),
                            as_of=row["as_of"])

    async def put_part_status(self, mpn_key: str, statuses: list[dict],
                              as_of: datetime) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO cache_part (mpn_key, status_json, as_of)"
                " VALUES ($1, $2, $3) ON CONFLICT (mpn_key) DO UPDATE SET"
                " status_json = EXCLUDED.status_json, as_of = EXCLUDED.as_of",
                mpn_key, json.dumps(statuses), as_of)

    @staticmethod
    def _offers(rows) -> list[CachedOffer]:
        return [CachedOffer(listing_key=r["listing_key"],
                            distributor=r["distributor"], sku=r["sku"],
                            part_key=r["part_key"],
                            listing=json.loads(r["listing_json"]),
                            as_of=r["as_of"]) for r in rows]

    async def get_offers(self, part_keys: list[str]) -> list[CachedOffer]:
        if not part_keys:
            return []
        async with self._timed("get_offers") as conn:
            rows = await conn.fetch(
                "SELECT listing_key, distributor, sku, part_key, listing_json,"
                " as_of FROM cache_offers WHERE part_key = ANY($1::text[])",
                part_keys)
        return self._offers(rows)

    async def get_offers_by_sku(self, pairs: list[tuple[str, str]]
                                ) -> list[CachedOffer]:
        """Rows for specific (distributor, sku) pairs.

        By sku rather than part_key because the caller is asking what we
        already hold for this exact offer, and the part_key on a row is only
        where the last merge filed it, which can move.

        Unnesting two arrays does the whole batch in one statement, so unlike
        SQLite there is no bound parameter ceiling to chunk around.
        """
        if not pairs:
            return []
        distributors = [p[0] for p in pairs]
        skus = [p[1] for p in pairs]
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT o.listing_key, o.distributor, o.sku, o.part_key,"
                " o.listing_json, o.as_of FROM cache_offers o"
                " JOIN unnest($1::text[], $2::text[]) AS p(distributor, sku)"
                " ON o.distributor = p.distributor AND o.sku = p.sku",
                distributors, skus)
        return self._offers(rows)

    async def put_offers(self, offers: list[CachedOffer]) -> None:
        """Write the whole batch in one statement.

        A single search writes one row per listing per distributor, which runs
        to a hundred or so, and sending them one at a time is the slowest thing
        the write path does against a hosted database.

        Postgres will not let one INSERT touch the same row twice, so the batch
        is collapsed by key first. Keeping the last row for a key is what
        separate writes would have left behind anyway.
        """
        if not offers:
            return
        latest: dict[tuple[str, str, str], CachedOffer] = {
            (o.listing_key, o.distributor, o.sku): o for o in offers}
        rows = list(latest.values())
        async with self._pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO cache_offers (listing_key, distributor, sku,"
                " part_key, listing_json, as_of)"
                " SELECT * FROM unnest($1::text[], $2::text[], $3::text[],"
                " $4::text[], $5::text[], $6::timestamptz[])"
                " ON CONFLICT (listing_key, distributor, sku) DO UPDATE SET"
                " part_key = EXCLUDED.part_key,"
                " listing_json = EXCLUDED.listing_json, as_of = EXCLUDED.as_of",
                [o.listing_key for o in rows], [o.distributor for o in rows],
                [o.sku for o in rows], [o.part_key for o in rows],
                [json.dumps(o.listing) for o in rows], [o.as_of for o in rows])

    async def find_part_key_by_sku(self, distributor: str,
                                   sku: str) -> str | None:
        async with self._pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT part_key FROM cache_offers"
                " WHERE distributor = $1 AND sku = $2 LIMIT 1",
                distributor, sku)

    async def get_parametric(self, key: str
                             ) -> tuple[list[dict], datetime] | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT rows_json, as_of FROM cache_parametric WHERE key = $1",
                key)
        if row is None:
            return None
        return json.loads(row["rows_json"]), row["as_of"]

    async def put_parametric(self, key: str, rows: list[dict],
                             as_of: datetime) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO cache_parametric (key, rows_json, as_of)"
                " VALUES ($1, $2, $3) ON CONFLICT (key) DO UPDATE SET"
                " rows_json = EXCLUDED.rows_json, as_of = EXCLUDED.as_of",
                key, json.dumps(rows), as_of)

    async def prune(self, before: datetime) -> int:
        """Drop rows too old to be served, and report how many.

        The horizon is deliberately much longer than the offer TTL: the
        offers table doubles as the SKU index behind the legacy C code
        redirect, and that lookup does not check freshness.
        """
        removed = 0
        async with self._pool.acquire() as conn:
            for table in _PRUNABLE:
                status = await conn.execute(
                    f"DELETE FROM {table} WHERE as_of < $1", before)
                removed += _deleted(status)
        return removed

    async def get_quota_markers(self) -> dict[str, datetime]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT distributor, resets_at FROM cache_quota_state")
        return {r["distributor"]: r["resets_at"] for r in rows}

    async def put_quota_marker(self, distributor: str,
                               resets_at: datetime) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO cache_quota_state (distributor, resets_at)"
                " VALUES ($1, $2) ON CONFLICT (distributor) DO UPDATE SET"
                " resets_at = EXCLUDED.resets_at",
                distributor, resets_at)
