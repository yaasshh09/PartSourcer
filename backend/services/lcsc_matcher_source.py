"""What the equivalent matcher needs from LCSC, and nothing else.

The matcher is v1 logic that reasons over LCSC parametric data, and this
sub-project does not change it. It wants get_part and list_parametric, so
this hands it both over LcscAdapter rather than keeping a second jlcsearch
client alive purely to satisfy the shape.
"""

from models.parametric import ParametricPart
from models.part import PartDetail
from services.adapters.base import RawListing
from services.adapters.lcsc import LcscAdapter


def _to_detail(listing: RawListing) -> PartDetail:
    return PartDetail(
        lcsc=listing.sku, mpn=listing.mpn, brand=listing.brand,
        package=listing.package, description=listing.description,
        stock=listing.stock, price_usd=listing.price,
        price_breaks=listing.price_breaks, stock_breakdown=None,
        is_basic=listing.is_basic, is_preferred=listing.is_preferred,
        datasheet_url=listing.datasheet_url, as_of=listing.as_of)


class LcscMatcherSource:
    def __init__(self, adapter: LcscAdapter):
        self._adapter = adapter

    async def get_part(self, lcsc_code: str,
                       refresh: bool = False) -> PartDetail | None:
        listing = await self._adapter.lookup_sku(lcsc_code)
        return None if listing is None else _to_detail(listing)

    async def list_parametric(self, category: str, package: str,
                              resistance_ohms: float | None = None
                              ) -> list[ParametricPart]:
        return await self._adapter.list_parametric(category, package,
                                                   resistance_ohms)
