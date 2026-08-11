import httpx
import pytest

from services.adapters.base import ParametricCapable, UpstreamError
from services.adapters.lcsc import LcscAdapter

pytestmark = pytest.mark.anyio

ROW = {"lcsc": 8734, "mfr": "STM32F103C8T6", "package": "LQFP-48",
       "description": "ARM MCU", "stock": 12400, "price": 1.8234,
       "is_basic": True, "is_preferred": False}


def client_returning(payload, status=200):
    def handler(request):
        return httpx.Response(status, json=payload)
    return httpx.AsyncClient(transport=httpx.MockTransport(handler),
                             base_url="https://jlcsearch.test")


async def test_search_maps_a_row_to_a_raw_listing():
    async with client_returning({"components": [ROW]}) as c:
        out = await LcscAdapter(c).search("stm32", limit=20)
    assert len(out) == 1
    r = out[0]
    assert (r.distributor, r.sku, r.mpn) == ("lcsc", "C8734", "STM32F103C8T6")
    assert (r.stock, r.in_stock, r.price, r.currency) == (12400, True, 1.8234, "USD")


async def test_lcsc_gaps_stay_null():
    async with client_returning({"components": [ROW]}) as c:
        r = (await LcscAdapter(c).search("stm32", limit=20))[0]
    assert r.brand is None and r.datasheet_url is None and r.price_breaks is None


async def test_product_url_is_the_jlcpcb_product_page():
    async with client_returning({"components": [ROW]}) as c:
        r = (await LcscAdapter(c).search("stm32", limit=20))[0]
    assert r.product_url == "https://jlcpcb.com/partdetail/C8734"


async def test_zero_stock_is_not_in_stock():
    async with client_returning({"components": [dict(ROW, stock=0)]}) as c:
        r = (await LcscAdapter(c).search("stm32", limit=20))[0]
    assert r.stock == 0 and r.in_stock is False


async def test_lookup_mpn_filters_to_the_matching_part():
    rows = [ROW, dict(ROW, lcsc=9999, mfr="STM32F103CBT6")]
    async with client_returning({"components": rows}) as c:
        out = await LcscAdapter(c).lookup_mpn("stm32f103c8t6")
    assert [r.sku for r in out] == ["C8734"]


async def test_empty_query_returns_empty_without_calling_upstream():
    called = []

    def handler(request):
        called.append(request.url)
        return httpx.Response(200, json={"components": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler),
                                 base_url="https://jlcsearch.test") as c:
        assert await LcscAdapter(c).search("   ", limit=20) == []
    assert called == []


async def test_upstream_500_raises_unavailable():
    async with client_returning({}, status=500) as c:
        with pytest.raises(UpstreamError) as exc:
            await LcscAdapter(c).search("stm32", limit=20)
    assert exc.value.kind == "unavailable"


async def test_adapter_is_parametric_capable():
    async with client_returning({"components": []}) as c:
        assert isinstance(LcscAdapter(c), ParametricCapable)
