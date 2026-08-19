"""SQLite specific cache store behaviour.

Everything true of any cache, rather than of a file on disk, moved to
test_cache_store_contract.py so that the Postgres store is held to the same
suite. What is left here is about the file itself: rebuilding an old one, and
reopening a current one.
"""

import sqlite3
from datetime import datetime, timezone

import pytest

from cache.store import CACHE_SCHEMA_VERSION, CachedOffer, SqliteCacheStore

pytestmark = pytest.mark.anyio

AS_OF = datetime(2026, 8, 14, 9, 14, tzinfo=timezone.utc)


def offer(listing_key="PART-A", distributor="lcsc", sku="C1", part_key=None):
    return CachedOffer(listing_key=listing_key, distributor=distributor,
                       sku=sku, part_key=part_key or listing_key,
                       listing={"mpn": listing_key}, as_of=AS_OF)


async def test_a_v1_database_is_dropped_and_rebuilt(tmp_path):
    """The cache holds no source of truth, so rebuilding is free and correct."""
    path = str(tmp_path / "old.db")
    conn = sqlite3.connect(path)
    conn.executescript(
        "CREATE TABLE parts (lcsc TEXT PRIMARY KEY, specs_json TEXT);"
        "INSERT INTO parts VALUES ('C8734', '{}');")
    conn.commit()
    conn.close()

    s = SqliteCacheStore(path)
    s.open()
    try:
        with sqlite3.connect(path) as check:
            names = {r[0] for r in check.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            version = check.execute("SELECT version FROM schema_meta").fetchone()[0]
    finally:
        s.close()

    assert "parts" not in names
    assert {"offers", "search_cache", "part_cache", "quota_state"} <= names
    assert version == CACHE_SCHEMA_VERSION


async def test_opening_a_current_database_twice_keeps_its_rows(tmp_path):
    path = str(tmp_path / "c.db")
    first = SqliteCacheStore(path)
    first.open()
    await first.put_offers([offer()])
    first.close()

    second = SqliteCacheStore(path)
    second.open()
    try:
        assert len(await second.get_offers(["PART-A"])) == 1
    finally:
        second.close()
