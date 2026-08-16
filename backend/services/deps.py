"""Dependency wiring: one shared HTTP client, the cache, and the services.

Swapping to the official LCSC API later = build a different adapter here.
CachedPartService wraps whatever PartService was handed; nothing else changes.
"""

import httpx

from cache.cached_part_service import CachedPartService
from cache.store import SqliteCacheStore
from config import settings
from history.store import HistoryStore, PostgresHistoryStore
from services.adapters.lcsc import LcscAdapter
from services.lcsc_matcher_source import LcscMatcherSource
from services.part_service import PartService, build_part_service
from services.throttle import RefreshThrottle

_client: httpx.AsyncClient | None = None
_store: SqliteCacheStore | None = None
_history_store: HistoryStore | None = None
_part_service: PartService | None = None
_cached_service: CachedPartService | None = None
_lcsc_adapter: LcscAdapter | None = None
_matcher_source: LcscMatcherSource | None = None
_distributor_clients: list[httpx.AsyncClient] = []


async def startup() -> None:
    global _client, _store, _history_store, _part_service
    global _cached_service, _lcsc_adapter, _matcher_source, _distributor_clients
    _client = httpx.AsyncClient(
        base_url=settings.jlcsearch_base_url,
        timeout=settings.request_timeout_secs,
        follow_redirects=True,
    )
    _store = SqliteCacheStore(settings.sqlite_path)
    _store.open()
    _lcsc_adapter = LcscAdapter(_client)
    _matcher_source = LcscMatcherSource(_lcsc_adapter)
    _part_service, _distributor_clients = build_part_service(settings, _client)
    # The exhaustion marker outlives the process only where the volume does.
    _part_service.attach_quota_markers(_store, await _store.get_quota_markers())
    _cached_service = CachedPartService(
        service=_part_service, store=_store,
        offer_ttl_secs=settings.stock_cache_ttl_secs,
        throttle=RefreshThrottle(settings.refresh_cooldown_secs))
    if settings.database_url:
        pg = PostgresHistoryStore(settings.database_url)
        await pg.open()
        _history_store = pg


async def shutdown() -> None:
    global _client, _store, _history_store, _part_service
    global _cached_service, _lcsc_adapter, _matcher_source, _distributor_clients
    if _history_store is not None and hasattr(_history_store, "close"):
        await _history_store.close()
    if _store is not None:
        _store.close()
    for distributor_client in _distributor_clients:
        await distributor_client.aclose()
    _distributor_clients = []
    _part_service = None
    _cached_service = None
    _lcsc_adapter = None
    _matcher_source = None
    if _client is not None:
        await _client.aclose()
    _client = None
    _store = None
    _history_store = None


def get_history_store() -> HistoryStore | None:
    """None when DATABASE_URL is unset. The recorder endpoint 503s in that case."""
    return _history_store


def get_cached_service() -> CachedPartService:
    assert _cached_service is not None, "cache not initialized (lifespan not run)"
    return _cached_service


def get_lcsc_adapter() -> LcscAdapter:
    assert _lcsc_adapter is not None, "adapter not initialized (lifespan not run)"
    return _lcsc_adapter


def get_matcher_source() -> LcscMatcherSource:
    assert _matcher_source is not None, "matcher source not initialized"
    return _matcher_source
