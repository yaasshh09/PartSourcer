import json
import pathlib

import httpx
import pytest

from services.adapters.base import UpstreamError
from services.adapters.digikey import DigiKeyAdapter
from services.adapters.digikey_auth import DigiKeyTokenClient

pytestmark = pytest.mark.anyio

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "digikey"

PRODUCT = {
    "ManufacturerProductNumber": "STM32F103C8T6",
    "Manufacturer": {"Name": "STMicroelectronics"},
    "Description": {"ProductDescription": "ARM MCU"},
    "DatasheetUrl": "https://example.test/ds.pdf",
    "ProductUrl": "https://digikey.test/p/497",
    "QuantityAvailable": 842,
    "UnitPrice": 3.11,
    "ProductVariations": [{
        "DigiKeyProductNumber": "497-6063-ND",
        "StandardPricing": [{"BreakQuantity": 1, "UnitPrice": 3.11},
                            {"BreakQuantity": 100, "UnitPrice": 2.24}],
    }],
}


def make(payload, status=200):
    def handler(request):
        if request.url.path.endswith("/token"):
            return httpx.Response(200, json={"access_token": "A", "expires_in": 600})
        return httpx.Response(status, json=payload)

    c = httpx.AsyncClient(transport=httpx.MockTransport(handler),
                          base_url="https://api.digikey.test")
    return DigiKeyAdapter(c, DigiKeyTokenClient(c, "id", "sec"), "id"), c


async def test_maps_a_product_to_a_raw_listing():
    a, c = make({"Products": [PRODUCT]})
    async with c:
        r = (await a.search("stm32", limit=10))[0]
    assert (r.distributor, r.sku, r.mpn) == ("digikey", "497-6063-ND", "STM32F103C8T6")
    assert (r.stock, r.in_stock, r.price, r.currency) == (842, True, 3.11, "USD")


async def test_fills_brand_datasheet_and_ladder():
    a, c = make({"Products": [PRODUCT]})
    async with c:
        r = (await a.search("stm32", limit=10))[0]
    assert r.brand == "STMicroelectronics"
    assert r.datasheet_url == "https://example.test/ds.pdf"
    assert r.price_breaks == [{"qty": 1, "price_usd": 3.11},
                              {"qty": 100, "price_usd": 2.24}]


async def test_product_without_variations_still_maps_with_empty_sku():
    p = dict(PRODUCT)
    p.pop("ProductVariations")
    a, c = make({"Products": [p]})
    async with c:
        r = (await a.search("stm32", limit=10))[0]
    assert r.sku == "" and r.price_breaks is None and r.price == 3.11


async def test_zero_quantity_is_not_in_stock():
    a, c = make({"Products": [dict(PRODUCT, QuantityAvailable=0)]})
    async with c:
        r = (await a.search("stm32", limit=10))[0]
    assert r.in_stock is False


async def test_429_raises_quota_kind():
    a, c = make({}, status=429)
    async with c:
        with pytest.raises(UpstreamError) as exc:
            await a.search("stm32", limit=10)
    assert exc.value.kind == "quota"


async def test_401_invalidates_the_token_and_retries_once():
    seen = {"product_calls": 0, "token_calls": 0}

    def handler(request):
        if request.url.path.endswith("/token"):
            seen["token_calls"] += 1
            return httpx.Response(200, json={"access_token": "A", "expires_in": 600})
        seen["product_calls"] += 1
        if seen["product_calls"] == 1:
            return httpx.Response(401, json={})
        return httpx.Response(200, json={"Products": [PRODUCT]})

    c = httpx.AsyncClient(transport=httpx.MockTransport(handler),
                          base_url="https://api.digikey.test")
    a = DigiKeyAdapter(c, DigiKeyTokenClient(c, "id", "sec"), "id")
    async with c:
        out = await a.search("stm32", limit=10)
    assert len(out) == 1
    assert seen["product_calls"] == 2 and seen["token_calls"] == 2


async def test_persistent_401_raises_rather_than_looping():
    a, c = make({}, status=401)
    async with c:
        with pytest.raises(UpstreamError):
            await a.search("stm32", limit=10)


async def test_sends_usd_and_client_id_headers():
    seen = {}

    def handler(request):
        if request.url.path.endswith("/token"):
            return httpx.Response(200, json={"access_token": "A", "expires_in": 600})
        seen.update(request.headers)
        return httpx.Response(200, json={"Products": []})

    c = httpx.AsyncClient(transport=httpx.MockTransport(handler),
                          base_url="https://api.digikey.test")
    a = DigiKeyAdapter(c, DigiKeyTokenClient(c, "id", "sec"), "id")
    async with c:
        await a.search("stm32", limit=10)
    assert seen["x-digikey-locale-currency"] == "USD"
    assert seen["x-digikey-client-id"] == "id"
    assert seen["authorization"] == "Bearer A"


async def test_real_fixture_parses_without_error():
    path = FIXTURES / "keyword_0.json"
    if not path.exists():
        pytest.skip("digikey fixtures not captured yet")
    a, c = make(json.loads(path.read_text(encoding="utf-8")))
    async with c:
        out = await a.search("STM32F103C8T6", limit=10)
    assert all(r.distributor == "digikey" for r in out)
