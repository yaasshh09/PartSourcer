"""Dependency wiring: one shared HTTP client + cached datasource.

Swapping to the official LCSC API later = construct a different inner
PartDataSource here. The cache wraps whatever is underneath; nothing
else changes.
"""

import httpx

from cache.caching_datasource import CachingPartDataSource
from cache.store import SqliteCacheStore
from config import settings
from services.datasource import JlcSearchDataSource, PartDataSource

_client: httpx.AsyncClient | None = None
_store: SqliteCacheStore | None = None
_datasource: PartDataSource | None = None


async def startup() -> None:
    global _client, _store, _datasource
    _client = httpx.AsyncClient(
        base_url=settings.jlcsearch_base_url,
        timeout=settings.request_timeout_secs,
        follow_redirects=True,
    )
    _store = SqliteCacheStore(settings.sqlite_path)
    _store.open()
    _datasource = CachingPartDataSource(
        inner=JlcSearchDataSource(_client),
        store=_store,
        specs_ttl_secs=settings.specs_cache_ttl_secs,
        stock_ttl_secs=settings.stock_cache_ttl_secs,
    )


async def shutdown() -> None:
    global _client, _store, _datasource
    if _store is not None:
        _store.close()
    if _client is not None:
        await _client.aclose()
    _client = None
    _store = None
    _datasource = None


def get_datasource() -> PartDataSource:
    assert _datasource is not None, "datasource not initialized (lifespan not run)"
    return _datasource
