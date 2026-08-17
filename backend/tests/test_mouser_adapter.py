import json
import pathlib

import httpx
import pytest

from services.adapters.base import UpstreamError
from services.adapters.mouser import MouserAdapter, parse_money

pytestmark = pytest.mark.anyio

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "mouser"


def load(name):
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def client_returning(payload, status=200):
    def handler(request):
        return httpx.Response(status, json=payload)
    return httpx.AsyncClient(transport=httpx.MockTransport(handler),
                             base_url="https://api.mouser.test")


PART = {
    "MouserPartNumber": "511-STM32F103C8T6",
    "ManufacturerPartNumber": "STM32F103C8T6",
    "Manufacturer": "STMicroelectronics",
    "Description": "ARM Microcontrollers",
    "DataSheetUrl": "https://example.test/ds.pdf",
    "ProductDetailUrl": "https://mouser.test/p/511",
    "AvailabilityInStock": "3150",
    "PriceBreaks": [{"Quantity": 1, "Price": "$2.94", "Currency": "USD"},
                    {"Quantity": 100, "Price": "$2.10", "Currency": "USD"}],
}


def body(parts, errors=None):
    return {"Errors": errors or [], "SearchResults": {"Parts": parts}}


@pytest.mark.parametrize("text,expected", [
    ("$2.94", (2.94, "USD")),
    ("2.94", (2.94, "USD")),
    ("$1,234.50", (1234.50, "USD")),
    ("", None),
    ("N/A", None),
    (None, None),
])
def test_parse_money(text, expected):
    assert parse_money(text) == expected


async def test_maps_a_part_to_a_raw_listing():
    async with client_returning(body([PART])) as c:
        r = (await MouserAdapter(c, "k").search("stm32", limit=10))[0]
    assert (r.distributor, r.sku, r.mpn) == (
        "mouser", "511-STM32F103C8T6", "STM32F103C8T6")
    assert (r.price, r.currency, r.stock, r.in_stock) == (2.94, "USD", 3150, True)


async def test_fills_the_gaps_lcsc_cannot():
    async with client_returning(body([PART])) as c:
        r = (await MouserAdapter(c, "k").search("stm32", limit=10))[0]
    assert r.brand == "STMicroelectronics"
    assert r.datasheet_url == "https://example.test/ds.pdf"
    assert r.price_breaks == [{"qty": 1, "price_usd": 2.94},
                              {"qty": 100, "price_usd": 2.10}]


async def test_missing_price_breaks_means_no_price_and_no_ladder():
    # Mouser omits pricing on quote-only parts. A 0.0 here reads as free.
    async with client_returning(body([dict(PART, PriceBreaks=[])])) as c:
        r = (await MouserAdapter(c, "k").search("stm32", limit=10))[0]
    assert r.price is None and r.price_breaks is None


async def test_an_unparseable_price_is_no_price():
    async with client_returning(
            body([dict(PART, PriceBreaks=[{"Quantity": 1, "Price": "N/A"}])])) as c:
        r = (await MouserAdapter(c, "k").search("stm32", limit=10))[0]
    assert r.price is None


async def test_unparseable_stock_becomes_zero():
    async with client_returning(body([dict(PART, AvailabilityInStock="")])) as c:
        r = (await MouserAdapter(c, "k").search("stm32", limit=10))[0]
    assert r.stock == 0 and r.in_stock is False


async def test_api_errors_block_raises_unavailable():
    payload = body([], errors=[{"Message": "Invalid API key"}])
    async with client_returning(payload) as c:
        with pytest.raises(UpstreamError) as exc:
            await MouserAdapter(c, "k").search("stm32", limit=10)
    assert exc.value.kind == "unavailable"
    assert "Invalid API key" in str(exc.value)


async def test_http_429_raises_quota_kind():
    async with client_returning({}, status=429) as c:
        with pytest.raises(UpstreamError) as exc:
            await MouserAdapter(c, "k").search("stm32", limit=10)
    assert exc.value.kind == "quota"


async def test_timeout_raises_timeout_kind():
    def handler(request):
        raise httpx.TimeoutException("slow", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler),
                                 base_url="https://api.mouser.test") as c:
        with pytest.raises(UpstreamError) as exc:
            await MouserAdapter(c, "k").search("stm32", limit=10)
    assert exc.value.kind == "timeout"


async def test_api_key_is_sent_as_a_query_param_not_a_header():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        return httpx.Response(200, json=body([]))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler),
                                 base_url="https://api.mouser.test") as c:
        await MouserAdapter(c, "secretkey").search("stm32", limit=10)
    assert "apiKey=secretkey" in seen["url"]


async def test_real_fixture_parses_without_error():
    if not (FIXTURES / "keyword_0.json").exists():
        pytest.skip("fixtures not captured yet")
    async with client_returning(load("keyword_0")) as c:
        out = await MouserAdapter(c, "k").search("STM32F103C8T6", limit=10)
    assert all(r.distributor == "mouser" and r.mpn for r in out)
