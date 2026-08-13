"""Dependency wiring: one shared HTTP client + cached datasource.

Swapping to the official LCSC API later = construct a different inner
PartDataSource here. The cache wraps whatever is underneath; nothing
else changes.
"""

import httpx

from cache.caching_datasource import CachingPartDataSource
from cache.store import SqliteCacheStore
from config import settings
from history.store import HistoryStore, PostgresHistoryStore
from services.datasource import JlcSearchDataSource, PartDataSource
from services.part_service import PartService, build_part_service
from services.throttle import RefreshThrottle

_client: httpx.AsyncClient | None = None
_store: SqliteCacheStore | None = None
_datasource: PartDataSource | None = None
_history_store: HistoryStore | None = None
_part_service: PartService | None = None
_distributor_clients: list[httpx.AsyncClient] = []


async def startup() -> None:
    global _client, _store, _datasource, _history_store, _part_service, _distributor_clients
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
        throttle=RefreshThrottle(settings.refresh_cooldown_secs),
    )
    _part_service, _distributor_clients = build_part_service(settings, _client)
    if settings.database_url:
        pg = PostgresHistoryStore(settings.database_url)
        await pg.open()
        _history_store = pg


async def shutdown() -> None:
    global _client, _store, _datasource, _history_store, _part_service, _distributor_clients
    if _history_store is not None and hasattr(_history_store, "close"):
        await _history_store.close()
    if _store is not None:
        _store.close()
    for distributor_client in _distributor_clients:
        await distributor_client.aclose()
    _distributor_clients = []
    _part_service = None
    if _client is not None:
        await _client.aclose()
    _client = None
    _store = None
    _datasource = None
    _history_store = None


def get_datasource() -> PartDataSource:
    assert _datasource is not None, "datasource not initialized (lifespan not run)"
    return _datasource


def get_history_store() -> HistoryStore | None:
    """None when DATABASE_URL is unset. The recorder endpoint 503s in that case."""
    return _history_store


def get_part_service() -> PartService:
    """SP1 part 3 points the routes at this. Nothing calls it yet."""
    assert _part_service is not None, "part service not initialized (lifespan not run)"
    return _part_service
