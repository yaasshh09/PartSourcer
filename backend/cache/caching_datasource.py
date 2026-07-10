"""Caching decorator over any PartDataSource (spec §7 + §5 honesty).

Owns all freshness decisions: search entries and part stock/price are
fresh for stock_ttl_secs; part specs for specs_ttl_secs (one upstream
fetch renews both — upstream has no stock-only call). Served as_of is
always the stored fetch time. Never stale-serves: a stale entry plus an
upstream failure propagates the UpstreamError.
"""

from datetime import datetime, timezone
from typing import Callable

from cache.store import SqliteCacheStore
from models.part import PartDetail
from models.search import SearchResult
from services.datasource import PartDataSource


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _specs(r: SearchResult) -> dict:
    return {"mpn": r.mpn, "brand": r.brand, "package": r.package,
            "description": r.description, "datasheet_url": r.datasheet_url}


def _detail_specs(d: PartDetail) -> dict:
    return {"mpn": d.mpn, "brand": d.brand, "package": d.package,
            "description": d.description, "datasheet_url": d.datasheet_url,
            "is_basic": d.is_basic, "is_preferred": d.is_preferred}


class CachingPartDataSource(PartDataSource):
    def __init__(self, inner: PartDataSource, store: SqliteCacheStore,
                 specs_ttl_secs: int, stock_ttl_secs: int,
                 now: Callable[[], datetime] = _utc_now):
        self._inner = inner
        self._store = store
        self._specs_ttl = specs_ttl_secs
        self._stock_ttl = stock_ttl_secs
        self._now = now

    def _fresh(self, as_of: datetime, ttl_secs: int) -> bool:
        return (self._now() - as_of).total_seconds() < ttl_secs

    async def _upsert(self, r: SearchResult) -> None:
        await self._store.upsert_part(r.lcsc, _specs(r), r.stock,
                                      r.price_usd, r.as_of, r.as_of)

    async def _upsert_detail(self, d: PartDetail) -> None:
        await self._store.upsert_part(d.lcsc, _detail_specs(d), d.stock,
                                      d.price_usd, d.as_of, d.as_of)

    async def search(self, query: str, page: int,
                     refresh: bool = False) -> list[SearchResult]:
        key = query.strip().lower()
        if not key:
            return []
        if not refresh:
            cached = await self._store.get_search(key, page)
            if cached is not None and self._fresh(cached[1], self._stock_ttl):
                return [SearchResult.model_validate(r) for r in cached[0]]
        results = await self._inner.search(query, page)
        as_of = results[0].as_of if results else self._now()
        rows = [r.model_dump(mode="json") for r in results]
        await self._store.put_search(key, page, rows, as_of)
        for r in results:  # write-through so get_part starts warm
            await self._upsert(r)
        return results

    async def get_part(self, lcsc_code: str,
                       refresh: bool = False) -> PartDetail | None:
        digits = lcsc_code.strip().upper().lstrip("C")
        if not digits.isdigit():
            return None
        key = f"C{digits}"
        if not refresh:
            p = await self._store.get_part(key)
            # Completeness: a search-warmed row lacks the flags. Only serve a
            # row that is fresh AND carries real flags — never a stale guess.
            if (p is not None
                    and self._fresh(p.stock_as_of, self._stock_ttl)
                    and self._fresh(p.specs_as_of, self._specs_ttl)
                    and p.specs.get("is_basic") is not None
                    and p.specs.get("is_preferred") is not None):
                return PartDetail(lcsc=p.lcsc, stock=p.stock,
                                  price_usd=p.price_usd,
                                  price_breaks=None, stock_breakdown=None,
                                  as_of=p.stock_as_of, **p.specs)
        detail = await self._inner.get_part(lcsc_code)
        if detail is not None:
            await self._upsert_detail(detail)
        return detail
