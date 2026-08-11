"""jlcsearch adapter (the v1 data source, now one distributor among three).

Mapping rationale lives in docs/jlcsearch-notes.md. The gaps are real and
stay null here: jlcsearch carries no brand, no datasheet, and no price
ladder. Mouser and DigiKey fill those in on their own offers.
"""

from datetime import datetime, timezone

import httpx

from models.parametric import ParametricPart
from services.adapters.base import DistributorAdapter, RawListing, UpstreamError
from services.datasource import _to_parametric


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

    def _to_listing(self, raw: dict, as_of: datetime) -> RawListing:
        code = f"C{raw['lcsc']}"
        stock = raw.get("stock") or 0
        return RawListing(
            distributor="lcsc",
            sku=code,
            mpn=raw.get("mfr") or "",
            brand=None,               # documented gap
            package=raw.get("package") or "",
            description=raw.get("description") or "",
            stock=stock,
            in_stock=stock > 0,
            price=round(raw.get("price") or raw.get("price1") or 0.0, 4),
            currency="USD",           # assumed, see docs/jlcsearch-notes.md
            price_breaks=None,        # documented gap
            datasheet_url=None,       # documented gap
            product_url=f"https://jlcpcb.com/partdetail/{code}",
            as_of=as_of,
        )

    async def search(self, query: str, limit: int) -> list[RawListing]:
        query = query.strip()
        if not query:
            return []
        items = await self._fetch_json("/api/search",
                                       {"q": query, "limit": limit}, "components")
        as_of = datetime.now(timezone.utc)
        return [self._to_listing(raw, as_of) for raw in items]

    async def lookup_mpn(self, mpn: str) -> list[RawListing]:
        listings = await self.search(mpn, limit=20)
        wanted = mpn.strip().upper()
        return [r for r in listings if r.mpn.upper() == wanted]

    async def list_parametric(self, category: str, package: str,
                              resistance_ohms: float | None = None
                              ) -> list[ParametricPart]:
        params: dict = {"package": package}
        if resistance_ohms is not None:
            # Upstream needs raw ohms; the '10k' suffix form is buggy (notes).
            n = int(resistance_ohms) if float(resistance_ohms).is_integer() \
                else resistance_ohms
            params["resistance"] = n
        items = await self._fetch_json(f"/{category}/list.json", params, category)
        return [_to_parametric(raw, category) for raw in items]
