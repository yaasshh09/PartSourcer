"""DigiKey Product Information adapter.

Currency is pinned to USD by header so no FX conversion is ever needed. A
401 invalidates the cached token and retries exactly once, because the
common cause is a token that expired between check and use.

DigiKey returns one product once per package type: cut tape, tape and reel,
Digi-Reel, sometimes a MarketPlace listing that ships from the supplier.
Each of those has its own SKU, its own price ladder, and its own stock, and
the product-level QuantityAvailable is the sum across all of them. Taking a
SKU and a price from one package type and the stock from that sum publishes
a quantity nobody can buy at the price shown, so one variation is chosen
here and every field on the listing comes from that same one.
"""

from datetime import datetime, timezone

import httpx

from services.adapters.base import (DistributorAdapter, RawListing,
                                    UpstreamError, priced)
from services.adapters.digikey_auth import DigiKeyTokenClient


def _number(value: object, default: float = 0.0) -> float:
    """Upstream numbers, defensively. One odd row must not kill a search."""
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _ladder(variation: dict) -> tuple[float | None, list[dict]]:
    """This package type's unit price and its full break ladder."""
    breaks = []
    for b in variation.get("StandardPricing") or []:
        step = priced(_number(b.get("UnitPrice")))
        if step is not None:
            breaks.append({"qty": int(_number(b.get("BreakQuantity"))),
                           "price_usd": step})
    breaks.sort(key=lambda b: b["qty"])
    return (breaks[0]["price_usd"] if breaks else None), breaks


def _variation_stock(variation: dict) -> int | None:
    """Stock for this package type, or None when DigiKey did not say."""
    qty = variation.get("QuantityAvailableforPackageType")
    return None if qty is None else int(_number(qty))


def _preference(variation: dict) -> tuple:
    """Sort key for picking one package type. Lower is better.

    MarketPlace ships direct from the supplier with its own shipping fee, so
    its unit price is not comparable to an ordinary DigiKey one and it only
    wins when it is the sole offer. After that the order is what a person
    sourcing a board actually wants: a real price, stock on the shelf, then
    the smallest order they are allowed to place. Cheapest breaks the tie,
    and the SKU breaks that, so upstream ordering never decides the answer.
    """
    price, _ = _ladder(variation)
    return (
        bool(variation.get("MarketPlace")),
        price is None,
        (_variation_stock(variation) or 0) <= 0,
        int(_number(variation.get("MinimumOrderQuantity"), 1.0) or 1),
        price if price is not None else float("inf"),
        str(variation.get("DigiKeyProductNumber") or ""),
    )


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
        variations = [v for v in product.get("ProductVariations") or []
                      if isinstance(v, dict)]
        chosen = min(variations, key=_preference) if variations else {}

        unit, breaks = _ladder(chosen)
        if unit is None:
            # Ranking puts priced package types first, so an unpriced choice
            # means none of them published a ladder. DigiKey's single-unit
            # product price is then the only price there is.
            unit = priced(_number(product.get("UnitPrice")))

        stock = _variation_stock(chosen)
        if stock is None:
            # QuantityAvailable is the sum across package types. With one
            # variation the sum is that variation. With several it belongs to
            # no single SKU, so this SKU's stock is simply unknown.
            stock = (int(_number(product.get("QuantityAvailable")))
                     if len(variations) <= 1 else 0)

        manufacturer = product.get("Manufacturer") or {}
        description = product.get("Description") or {}
        return RawListing(
            distributor="digikey",
            sku=chosen.get("DigiKeyProductNumber") or "",
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
