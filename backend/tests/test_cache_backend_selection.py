"""Which cache the app opens, and what it refuses to do.

The dangerous case is not an error, it is a silent success: a host running
several processes that quietly gets a per process SQLite file. Nothing fails,
nothing logs, and the only symptom is one part quoting two prices depending on
which instance answered. So the misconfiguration has to be loud.
"""

import pytest

from cache.pg_store import PostgresCacheStore
from cache.store import SqliteCacheStore
from config import settings
from services import deps

pytestmark = pytest.mark.anyio


@pytest.fixture
def restore():
    before = (settings.cache_backend, settings.database_url,
              settings.sqlite_path)
    yield
    (settings.cache_backend, settings.database_url,
     settings.sqlite_path) = before


async def test_the_default_is_a_sqlite_file(restore, tmp_path):
    settings.cache_backend = "sqlite"
    settings.sqlite_path = str(tmp_path / "c.db")

    store = await deps._open_cache()

    assert isinstance(store, SqliteCacheStore)
    store.close()


async def test_postgres_without_a_dsn_refuses_to_start(restore):
    settings.cache_backend = "postgres"
    settings.database_url = None

    with pytest.raises(RuntimeError) as exc:
        await deps._open_cache()

    assert "DATABASE_URL" in str(exc.value)


async def test_postgres_with_an_empty_dsn_refuses_too(restore):
    """An unset environment variable arrives as "", not as None."""
    settings.cache_backend = "postgres"
    settings.database_url = ""

    with pytest.raises(RuntimeError):
        await deps._open_cache()


async def test_an_unknown_backend_falls_back_to_sqlite(restore, tmp_path):
    """Safe direction to fail: SQLite is correct everywhere, just not shared."""
    settings.cache_backend = "redis-someday"
    settings.sqlite_path = str(tmp_path / "c.db")

    store = await deps._open_cache()

    assert isinstance(store, SqliteCacheStore)
    store.close()


@pytest.mark.live
async def test_postgres_backend_opens_a_pool(restore):
    import os
    dsn = os.environ.get("TEST_PG_DSN")
    if not dsn:
        pytest.skip("set TEST_PG_DSN to a throwaway database")
    settings.cache_backend = "postgres"
    settings.database_url = dsn

    store = await deps._open_cache()
    try:
        assert isinstance(store, PostgresCacheStore)
        assert await store.get_quota_markers() == {}
    finally:
        await store.close()
