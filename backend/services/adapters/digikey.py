"""DigiKey Product Information adapter.

Currency is pinned to USD by header so no FX conversion is ever needed. A
401 invalidates the cached token and retries exactly once, because the
common cause is a token that expired between check and use.
"""

from datetime import datetime, timezone

import httpx

from services.adapters.base import (DistributorAdapter, RawListing,
                                    UpstreamError, priced)
from services.adapters.digikey_auth import DigiKeyTokenClient


class DigiKeyAdapter(DistributorAdapter):
    name = "digikey"

    def __init__(self, client: httpx.AsyncClient,
                 token_client: DigiKeyTokenClient, client_id: str):
        self._client = client
        self._tokens = token_client
        self._client_id = client_id

    async def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {await self._tokens.token()}",
                "X-DIGIKEY-Client-Id": self._client_id,
                "X-DIGIKEY-Locale-Site": "US",
                "X-DIGIKEY-Locale-Currency": "USD"}

    async def _post(self, path: str, payload: dict, *, retry: bool = True) -> dict:
        try:
            resp = await self._client.post(path, headers=await self._headers(),
                                           json=payload)
        except httpx.TimeoutException as exc:
            raise UpstreamError("timeout", f"digikey timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            raise UpstreamError("unavailable", f"digikey unreachable: {exc}") from exc

        if resp.status_code == 401 and retry:
            self._tokens.invalidate()
            return await self._post(path, payload, retry=False)
        if resp.status_code == 429:
            raise UpstreamError("quota", "digikey rate limit reached")
        if resp.status_code != 200:
            raise UpstreamError("unavailable",
                                f"digikey returned HTTP {resp.status_code}")
        try:
            data = resp.json()
        except ValueError as exc:
            raise UpstreamError("unavailable", "digikey returned non-JSON") from exc
        if not isinstance(data, dict):
            raise UpstreamError("unavailable",
                                "digikey returned a non-object JSON body")
        return data

    def _to_listing(self, product: dict, as_of: datetime,
                    rank: int = 0) -> RawListing:
        variations = product.get("ProductVariations") or []
        first = variations[0] if variations else {}
        breaks = []
        for b in first.get("StandardPricing") or []:
            step = priced(float(b.get("UnitPrice") or 0.0))
            if step is not None:
                breaks.append({"qty": int(b.get("BreakQuantity") or 0),
                               "price_usd": step})
        breaks.sort(key=lambda b: b["qty"])
        unit = (breaks[0]["price_usd"] if breaks
                else priced(float(product.get("UnitPrice") or 0.0)))

        stock = int(product.get("QuantityAvailable") or 0)
        manufacturer = product.get("Manufacturer") or {}
        description = product.get("Description") or {}
        return RawListing(
            distributor="digikey",
            sku=first.get("DigiKeyProductNumber") or "",
            mpn=product.get("ManufacturerProductNumber") or "",
            brand=manufacturer.get("Name") or None,
            package="",
            description=description.get("ProductDescription") or "",
            stock=stock,
            in_stock=stock > 0,
            price=unit,
            currency="USD",           # pinned by the locale header
            price_breaks=breaks or None,
            datasheet_url=product.get("DatasheetUrl") or None,
            product_url=product.get("ProductUrl") or None,
            as_of=as_of,
            rank=rank,
        )

    async def _keyword(self, keyword: str, limit: int) -> list[RawListing]:
        keyword = keyword.strip()
        if not keyword:
            return []
        data = await self._post("/products/v4/search/keyword",
                                {"Keywords": keyword, "Limit": limit, "Offset": 0})
        as_of = datetime.now(timezone.utc)
        return [self._to_listing(p, as_of, rank=i)
                for i, p in enumerate(data.get("Products") or [])]

    async def search(self, query: str, limit: int) -> list[RawListing]:
        return await self._keyword(query, limit)

    async def lookup_mpn(self, mpn: str, limit: int = 20) -> list[RawListing]:
        return await self._keyword(mpn, limit)
