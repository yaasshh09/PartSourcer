"""Mouser Search API adapter.

Mouser returns money as a display string ("$2.94") and stock as a string
of digits, so every numeric field is parsed defensively and falls back to
a value that reads as "unknown" rather than a guess.
"""

import re
from datetime import datetime, timezone

import httpx

from services.adapters.base import (DistributorAdapter, RawListing,
                                    UpstreamError, priced)

_MONEY = re.compile(r"-?\d[\d,]*\.?\d*")


def parse_money(text: str | None) -> tuple[float, str] | None:
    """Parse "$2.94" into (2.94, "USD"). None when there is no number."""
    if not text:
        return None
    m = _MONEY.search(text)
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", "")), "USD"
    except ValueError:
        return None


def _parse_int(text: object) -> int:
    try:
        return int(str(text).replace(",", "").strip())
    except (TypeError, ValueError):
        return 0


class MouserAdapter(DistributorAdapter):
    name = "mouser"

    def __init__(self, client: httpx.AsyncClient, api_key: str):
        self._client = client
        self._api_key = api_key

    async def _post(self, path: str, payload: dict) -> dict:
        try:
            resp = await self._client.post(
                path, params={"apiKey": self._api_key}, json=payload)
        except httpx.TimeoutException as exc:
            raise UpstreamError("timeout", f"mouser timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            raise UpstreamError("unavailable", f"mouser unreachable: {exc}") from exc
        if resp.status_code == 429:
            raise UpstreamError("quota", "mouser rate limit reached")
        if resp.status_code != 200:
            raise UpstreamError("unavailable",
                                f"mouser returned HTTP {resp.status_code}")
        try:
            data = resp.json()
        except ValueError as exc:
            raise UpstreamError("unavailable", "mouser returned non-JSON") from exc
        errors = data.get("Errors") or []
        if errors:
            first = errors[0].get("Message") or "unknown error"
            raise UpstreamError("unavailable", f"mouser error: {first}")
        return data

    def _to_listing(self, part: dict, as_of: datetime, rank: int = 0) -> RawListing:
        breaks = []
        for b in part.get("PriceBreaks") or []:
            parsed = parse_money(b.get("Price"))
            step = priced(parsed[0]) if parsed else None
            if step is not None:
                breaks.append({"qty": _parse_int(b.get("Quantity")),
                               "price_usd": step})
        breaks.sort(key=lambda b: b["qty"])
        unit = breaks[0]["price_usd"] if breaks else None
        currency = "USD"
        first_raw = (part.get("PriceBreaks") or [{}])[0]
        if first_raw.get("Currency"):
            currency = str(first_raw["Currency"]).upper()

        stock = _parse_int(part.get("AvailabilityInStock"))
        return RawListing(
            distributor="mouser",
            sku=part.get("MouserPartNumber") or "",
            mpn=part.get("ManufacturerPartNumber") or "",
            brand=part.get("Manufacturer") or None,
            package="",                  # not a first-class Mouser field
            description=part.get("Description") or "",
            stock=stock,
            in_stock=stock > 0,
            price=unit,
            currency=currency,
            price_breaks=breaks or None,
            datasheet_url=part.get("DataSheetUrl") or None,
            product_url=part.get("ProductDetailUrl") or None,
            as_of=as_of,
            rank=rank,
        )

    async def _keyword(self, keyword: str, limit: int) -> list[RawListing]:
        keyword = keyword.strip()
        if not keyword:
            return []
        data = await self._post("/api/v1/search/keyword", {
            "SearchByKeywordRequest": {"keyword": keyword, "records": limit,
                                       "startingRecord": 0}})
        parts = (data.get("SearchResults") or {}).get("Parts") or []
        as_of = datetime.now(timezone.utc)
        return [self._to_listing(p, as_of, rank=i) for i, p in enumerate(parts)]

    async def search(self, query: str, limit: int) -> list[RawListing]:
        return await self._keyword(query, limit)

    async def lookup_mpn(self, mpn: str, limit: int = 20) -> list[RawListing]:
        return await self._keyword(mpn, limit)
