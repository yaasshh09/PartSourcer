"""Swappable part-data source (spec §8).

Routes depend on the PartDataSource ABC only. JlcSearchDataSource is the v1
implementation over the jlcsearch API (see docs/jlcsearch-notes.md for the
verified upstream reality this mapping encodes). A future official-LCSC
datasource implements the same interface and swaps in via services/deps.py.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone

import httpx

from models.part import PartDetail
from models.parametric import ParametricPart
from models.search import SearchResult

PAGE_SIZE = 20


class UpstreamError(Exception):
    """Upstream failure, categorized so routes can map to HTTP codes."""

    def __init__(self, kind: str, detail: str):
        super().__init__(detail)
        self.kind = kind  # "timeout" | "unavailable"


# Shared by all route handlers: maps UpstreamError.kind -> HTTP status.
UPSTREAM_STATUS: dict[str, int] = {"timeout": 504, "unavailable": 502}


class PartDataSource(ABC):
    @abstractmethod
    async def search(self, query: str, page: int,
                     refresh: bool = False) -> list[SearchResult]: ...

    @abstractmethod
    async def get_part(self, lcsc_code: str,
                       refresh: bool = False) -> PartDetail | None: ...

    @abstractmethod
    async def list_parametric(self, category: str, package: str,
                              resistance_ohms: float | None = None
                              ) -> list[ParametricPart]: ...


def _to_result(raw: dict, as_of: datetime) -> SearchResult:
    """Map one upstream item to the §9 shape (see docs/jlcsearch-notes.md)."""
    return SearchResult(
        lcsc=f"C{raw['lcsc']}",
        mpn=raw.get("mfr") or "",
        brand=None,  # not in upstream data (documented gap)
        package=raw.get("package") or "",
        description=raw.get("description") or "",
        stock=raw.get("stock") or 0,
        price_usd=round(raw.get("price") or raw.get("price1") or 0.0, 4),
        datasheet_url=None,  # not in upstream data (documented gap)
        as_of=as_of,
    )


def _to_detail(raw: dict, as_of: datetime) -> PartDetail:
    """Map one upstream item to the §9 detail shape (see docs/jlcsearch-notes.md)."""
    return PartDetail(
        lcsc=f"C{raw['lcsc']}",
        mpn=raw.get("mfr") or "",
        brand=None,  # not in upstream data (documented gap)
        package=raw.get("package") or "",
        description=raw.get("description") or "",
        stock=raw.get("stock") or 0,
        price_usd=round(raw.get("price") or raw.get("price1") or 0.0, 4),
        price_breaks=None,   # no upstream ladder (honest gap)
        stock_breakdown=None,  # no upstream breakdown (honest gap)
        is_basic=raw.get("is_basic"),
        is_preferred=raw.get("is_preferred"),
        datasheet_url=None,  # not in upstream data (documented gap)
        as_of=as_of,
    )


_PARAMETRIC_SPEC_FIELDS = {
    "resistors": ("resistance", "tolerance_fraction", "power_watts"),
    "capacitors": ("capacitance_farads", "voltage_rating", "tolerance_fraction",
                   "temperature_coefficient"),
}


def _to_parametric(raw: dict, category: str) -> ParametricPart:
    """Map one parametric row to ParametricPart (see docs/jlcsearch-notes.md)."""
    fields = _PARAMETRIC_SPEC_FIELDS.get(category, ())
    return ParametricPart(
        lcsc=f"C{raw['lcsc']}",
        mpn=raw.get("mfr") or "",
        package=raw.get("package") or "",
        stock=raw.get("stock") or 0,
        price_usd=round(raw.get("price1") or 0.0, 4),
        in_stock=bool(raw.get("in_stock")),
        is_basic=raw.get("is_basic"),
        is_preferred=raw.get("is_preferred"),
        specs={f: raw.get(f) for f in fields},
    )


class JlcSearchDataSource(PartDataSource):
    def __init__(self, client: httpx.AsyncClient):
        self._client = client

    async def _fetch(self, query: str, limit: int) -> list[dict]:
        try:
            resp = await self._client.get(
                "/api/search", params={"q": query, "limit": limit})
        except httpx.TimeoutException as exc:
            raise UpstreamError("timeout", f"jlcsearch timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            raise UpstreamError("unavailable", f"jlcsearch unreachable: {exc}") from exc
        if resp.status_code != 200:
            raise UpstreamError(
                "unavailable", f"jlcsearch returned HTTP {resp.status_code}")
        try:
            data = resp.json()
        except ValueError as exc:
            raise UpstreamError("unavailable", "jlcsearch returned non-JSON") from exc
        items = data.get("components")
        if not isinstance(items, list):
            raise UpstreamError("unavailable", "jlcsearch response missing 'components'")
        return items

    async def search(self, query: str, page: int,
                     refresh: bool = False) -> list[SearchResult]:
        query = query.strip()
        if not query:
            return []
        # Upstream ignores `page`; fetch enough rows and window locally.
        items = await self._fetch(query, limit=page * PAGE_SIZE)
        as_of = datetime.now(timezone.utc)
        start = (page - 1) * PAGE_SIZE
        return [_to_result(raw, as_of) for raw in items[start:start + PAGE_SIZE]]

    async def get_part(self, lcsc_code: str,
                       refresh: bool = False) -> PartDetail | None:
        code = lcsc_code.strip().upper().lstrip("C")
        if not code.isdigit():
            return None
        items = await self._fetch(code, limit=PAGE_SIZE)
        as_of = datetime.now(timezone.utc)
        for raw in items:
            if str(raw.get("lcsc")) == code:
                return _to_detail(raw, as_of)
        return None

    async def _fetch_parametric(self, category: str, params: dict) -> list[dict]:
        try:
            resp = await self._client.get(f"/{category}/list.json", params=params)
        except httpx.TimeoutException as exc:
            raise UpstreamError("timeout", f"jlcsearch timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            raise UpstreamError("unavailable", f"jlcsearch unreachable: {exc}") from exc
        if resp.status_code != 200:
            raise UpstreamError(
                "unavailable", f"jlcsearch returned HTTP {resp.status_code}")
        try:
            data = resp.json()
        except ValueError as exc:
            raise UpstreamError("unavailable", "jlcsearch returned non-JSON") from exc
        items = data.get(category)
        if not isinstance(items, list):
            raise UpstreamError(
                "unavailable", f"jlcsearch response missing '{category}'")
        return items

    async def list_parametric(self, category: str, package: str,
                              resistance_ohms: float | None = None
                              ) -> list[ParametricPart]:
        params: dict = {"package": package}
        if resistance_ohms is not None:
            # Upstream needs raw ohms; the '10k' suffix form is buggy (notes).
            n = int(resistance_ohms) if float(resistance_ohms).is_integer() \
                else resistance_ohms
            params["resistance"] = n
        items = await self._fetch_parametric(category, params)
        return [_to_parametric(raw, category) for raw in items]
