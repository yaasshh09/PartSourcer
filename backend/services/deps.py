"""Dependency wiring: one shared HTTP client + datasource for the app.

Swapping to the official LCSC API later = construct a different
PartDataSource here. Nothing else changes.
"""

import httpx

from config import settings
from services.datasource import JlcSearchDataSource, PartDataSource

_client: httpx.AsyncClient | None = None
_datasource: PartDataSource | None = None


async def startup() -> None:
    global _client, _datasource
    _client = httpx.AsyncClient(
        base_url=settings.jlcsearch_base_url,
        timeout=settings.request_timeout_secs,
        follow_redirects=True,
    )
    _datasource = JlcSearchDataSource(_client)


async def shutdown() -> None:
    global _client, _datasource
    if _client is not None:
        await _client.aclose()
    _client = None
    _datasource = None


def get_datasource() -> PartDataSource:
    assert _datasource is not None, "datasource not initialized (lifespan not run)"
    return _datasource
