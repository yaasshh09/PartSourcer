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


async def test_a_product_with_no_pricing_at_all_has_no_price():
    p = dict(PRODUCT)
    p.pop("ProductVariations")
    p.pop("UnitPrice")
    a, c = make({"Products": [p]})
    async with c:
        r = (await a.search("stm32", limit=10))[0]
    assert r.price is None


async def test_a_zero_unit_price_is_no_price():
    # DigiKey sends 0.0 for call-for-quote products. It is not free.
    a, c = make({"Products": [dict(PRODUCT, UnitPrice=0.0,
                                   ProductVariations=[])]})
    async with c:
        r = (await a.search("stm32", limit=10))[0]
    assert r.price is None


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


# One product offered in three package types. The product-level quantity is
# the sum across all of them (11012), which is not buyable at any one SKU.
MULTI = dict(
    PRODUCT,
    QuantityAvailable=11012,
    ProductVariations=[
        {"DigiKeyProductNumber": "497-CUT-ND", "MarketPlace": False,
         "QuantityAvailableforPackageType": 12, "MinimumOrderQuantity": 1,
         "StandardPricing": [{"BreakQuantity": 1, "UnitPrice": 3.11}]},
        {"DigiKeyProductNumber": "497-REEL-ND", "MarketPlace": False,
         "QuantityAvailableforPackageType": 8000, "MinimumOrderQuantity": 4000,
         "StandardPricing": [{"BreakQuantity": 4000, "UnitPrice": 2.24}]},
        {"DigiKeyProductNumber": "497-DKR-ND", "MarketPlace": False,
         "QuantityAvailableforPackageType": 3000, "MinimumOrderQuantity": 1,
         "StandardPricing": [{"BreakQuantity": 1, "UnitPrice": 3.44}]},
    ],
)

MARKETPLACE = {"DigiKeyProductNumber": "MP-9999-ND", "MarketPlace": True,
               "QuantityAvailableforPackageType": 500, "MinimumOrderQuantity": 1,
               "StandardPricing": [{"BreakQuantity": 1, "UnitPrice": 0.99}]}


async def one(payload):
    a, c = make(payload)
    async with c:
        return (await a.search("stm32", limit=10))[0]


async def test_stock_comes_from_the_chosen_variation_not_the_product_sum():
    r = await one({"Products": [MULTI]})
    assert r.stock == 12, "11012 is the sum across package types, buyable at none"


async def test_sku_price_and_stock_all_describe_the_same_variation():
    r = await one({"Products": [MULTI]})
    chosen = [v for v in MULTI["ProductVariations"]
              if v["DigiKeyProductNumber"] == r.sku][0]
    assert r.price == chosen["StandardPricing"][0]["UnitPrice"]
    assert r.stock == chosen["QuantityAvailableforPackageType"]


async def test_the_variation_choice_ignores_upstream_ordering():
    forward = await one({"Products": [MULTI]})
    shuffled = dict(MULTI, ProductVariations=list(
        reversed(MULTI["ProductVariations"])))
    backward = await one({"Products": [shuffled]})
    assert (forward.sku, forward.price, forward.stock) == \
           (backward.sku, backward.price, backward.stock)


async def test_a_reel_only_minimum_does_not_beat_a_single_unit_offer():
    # 497-REEL-ND is cheaper per unit but you must buy 4000 of them.
    r = await one({"Products": [MULTI]})
    assert r.sku == "497-CUT-ND" and r.price == 3.11


async def test_marketplace_variations_lose_to_ordinary_ones():
    # MarketPlace ships direct from the supplier with its own shipping fee,
    # so its unit price is not comparable to a normal DigiKey price.
    p = dict(MULTI, ProductVariations=[MARKETPLACE] + MULTI["ProductVariations"])
    r = await one({"Products": [p]})
    assert r.sku == "497-CUT-ND"


async def test_a_marketplace_only_product_is_still_offered():
    p = dict(MULTI, ProductVariations=[MARKETPLACE])
    r = await one({"Products": [p]})
    assert (r.sku, r.price, r.stock) == ("MP-9999-ND", 0.99, 500)


async def test_an_unpriced_variation_loses_to_a_priced_one():
    bare = {"DigiKeyProductNumber": "497-BARE-ND", "MarketPlace": False,
            "QuantityAvailableforPackageType": 99999, "MinimumOrderQuantity": 1}
    p = dict(MULTI, ProductVariations=[bare] + MULTI["ProductVariations"])
    r = await one({"Products": [p]})
    assert r.sku == "497-CUT-ND"


async def test_an_out_of_stock_variation_loses_to_a_stocked_one():
    p = dict(MULTI, ProductVariations=[
        dict(MULTI["ProductVariations"][0], QuantityAvailableforPackageType=0),
        MULTI["ProductVariations"][2]])
    r = await one({"Products": [p]})
    assert r.sku == "497-DKR-ND" and r.stock == 3000


async def test_several_variations_without_quantities_do_not_borrow_the_sum():
    # With the per-package quantity missing we do not know this SKU's stock,
    # and the product-level sum belongs to no single SKU.
    p = dict(MULTI, ProductVariations=[
        {"DigiKeyProductNumber": "497-A-ND",
         "StandardPricing": [{"BreakQuantity": 1, "UnitPrice": 3.11}]},
        {"DigiKeyProductNumber": "497-B-ND",
         "StandardPricing": [{"BreakQuantity": 1, "UnitPrice": 3.44}]}])
    r = await one({"Products": [p]})
    assert r.stock == 0 and r.in_stock is False
