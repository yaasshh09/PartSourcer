"""jlcsearch adapter (the v1 data source, now one distributor among three).

Mapping rationale lives in docs/jlcsearch-notes.md. The gaps are real and
stay null here: jlcsearch carries no brand, no datasheet, and no price
ladder. Mouser and DigiKey fill those in on their own offers.
"""

import re
from datetime import datetime, timezone

import httpx

from models.parametric import ParametricPart
from services.adapters.base import (DistributorAdapter, RawListing,
                                    UpstreamError, priced)
from services.datasource import _to_parametric


def _mentions_any(raw: dict, query: str) -> bool:
    """Whether a search row names at least one word of the query.

    Upstream promises every word appears in its search text, but on
    2026-10-11 it had rebuilt its table without its text index, so a search
    for an MCU came back as capacitors with a 200. Its search text also covers
    category, manufacturer and attributes, which a row does not carry, so
    demanding every word here would drop real matches once it is fixed. One
    word in the MPN, package or description is the loosest check that still
    catches rows that were never about the query.
    """
    words = re.findall(r"[a-z0-9]+", query.lower())
    words = [w for w in words if len(w) > 1] or words
    text = " ".join(str(raw.get(f) or "")
                    for f in ("mfr", "package", "description")).lower()
    return any(w in text for w in words)


# Upstream wants raw ohms and raw farads: it reads 10k as 10 ohms and 100nF
# as nothing at all (notes).
_VALUE_FILTER = {"resistors": "resistance", "capacitors": "capacitance"}


def plain_number(value: float) -> str:
    """How a filter value is written upstream, and in the cache key for it.

    Nine significant digits drops binary noise, so the 100nF read off a
    description and the 1.0000000000000001e-07 in a spec row are one query.
    """
    return str(int(value)) if float(value).is_integer() else f"{value:.9g}"


class LcscAdapter(DistributorAdapter):
    name = "lcsc"

    def __init__(self, client: httpx.AsyncClient):
        self._client = client

    async def _fetch_json(self, path: str, params: dict, list_key: str) -> list[dict]:
        try:
            resp = await self._client.get(path, params=params)
        except httpx.TimeoutException as exc:
            raise UpstreamError("timeout", f"jlcsearch timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            raise UpstreamError("unavailable", f"jlcsearch unreachable: {exc}") from exc
        if resp.status_code != 200:
            raise UpstreamError("unavailable",
                                f"jlcsearch returned HTTP {resp.status_code}")
        try:
            data = resp.json()
        except ValueError as exc:
            raise UpstreamError("unavailable", "jlcsearch returned non-JSON") from exc
        if not isinstance(data, dict):
            raise UpstreamError("unavailable",
                                "jlcsearch returned a non-object JSON body")
        items = data.get(list_key)
        if not isinstance(items, list):
            raise UpstreamError("unavailable",
                                f"jlcsearch response missing '{list_key}'")
        return items

    def _to_listing(self, raw: dict, as_of: datetime, rank: int = 0) -> RawListing:
        code = f"C{raw['lcsc']}"
        stock = raw.get("stock") or 0
        price = priced(raw.get("price") or raw.get("price1"))
        return RawListing(
            distributor="lcsc",
            sku=code,
            mpn=raw.get("mfr") or "",
            brand=None,               # documented gap
            package=raw.get("package") or "",
            description=raw.get("description") or "",
            stock=stock,
            in_stock=stock > 0,
            price=None if price is None else round(price, 4),
            currency="USD",           # assumed, see docs/jlcsearch-notes.md
            price_breaks=None,        # documented gap
            datasheet_url=None,       # documented gap
            product_url=f"https://jlcpcb.com/partdetail/{code}",
            as_of=as_of,
            is_basic=raw.get("is_basic"),
            is_preferred=raw.get("is_preferred"),
            rank=rank,
        )

    async def _query(self, query: str, limit: int) -> list[dict]:
        return await self._fetch_json("/api/search",
                                      {"q": query, "limit": limit}, "components")

    def _listings(self, items: list[dict]) -> list[RawListing]:
        as_of = datetime.now(timezone.utc)
        return [self._to_listing(raw, as_of, rank=i)
                for i, raw in enumerate(items)]

    async def search(self, query: str, limit: int) -> list[RawListing]:
        query = query.strip()
        if not query:
            return []
        items = await self._query(query, limit)
        related = [raw for raw in items if _mentions_any(raw, query)]
        if items and not related:
            raise UpstreamError("unavailable",
                                "jlcsearch returned parts unrelated to the search")
        return self._listings(related)

    async def lookup_mpn(self, mpn: str, limit: int = 20) -> list[RawListing]:
        # Unfiltered: select_part takes the exact key and ignores the rest.
        mpn = mpn.strip()
        return self._listings(await self._query(mpn, limit)) if mpn else []

    async def lookup_sku(self, sku: str) -> RawListing | None:
        """Resolve an LCSC code to its listing. LCSC-only, and deliberately
        not on the ABC: nothing else needs SKU lookup yet.

        The limit=1 attempt comes first and is load-bearing. Upstream returns
        a different result set for the same part depending on `limit`: C25531
        comes back at limit=1 and yields {"components": []} at limit=20, both
        HTTP 200, stable across repeats. See docs/jlcsearch-notes.md.
        """
        code = sku.strip().upper().lstrip("C")
        if not code.isdigit():
            return None
        for query, limit in ((f"C{code}", 1), (code, 20)):
            items = await self._fetch_json("/api/search",
                                           {"q": query, "limit": limit},
                                           "components")
            as_of = datetime.now(timezone.utc)
            for i, raw in enumerate(items):
                if str(raw.get("lcsc")) == code:
                    return self._to_listing(raw, as_of, rank=i)
        return None

    async def list_parametric(self, category: str, package: str,
                              value: float | None = None
                              ) -> list[ParametricPart]:
        """A package's parametric rows, narrowed to one value when given.

        Upstream stops at 100 rows, so without the value an 0603 list holds
        a sliver of the package and most parts are simply not in it.
        """
        params: dict = {"package": package}
        if value is not None:
            params[_VALUE_FILTER[category]] = plain_number(value)
        items = await self._fetch_json(f"/{category}/list.json", params, category)
        return [_to_parametric(raw, category) for raw in items]

    async def list_category(self, path: str, envelope: str,
                            params: dict) -> list[dict]:
        """Raw rows from a parametric list, for browse. Prices come through
        here untouched; browse drops them when it maps each row."""
        return await self._fetch_json(path, params, envelope)
