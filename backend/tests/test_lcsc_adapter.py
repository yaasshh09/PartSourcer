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


async def test_a_row_with_no_price_carries_no_price():
    row = {k: v for k, v in ROW.items() if k != "price"}
    async with client_returning({"components": [row]}) as c:
        r = (await LcscAdapter(c).search("stm32", limit=20))[0]
    assert r.price is None


async def test_zero_stock_is_not_in_stock():
    async with client_returning({"components": [dict(ROW, stock=0)]}) as c:
        r = (await LcscAdapter(c).search("stm32", limit=20))[0]
    assert r.stock == 0 and r.in_stock is False


async def test_lookup_mpn_keeps_packaging_variants():
    """The adapter must not drop -TR: merge decides the tier, not the adapter.
    Filtering here made the detail page's variant group unreachable."""
    rows = [ROW, dict(ROW, lcsc=9999, mfr="STM32F103C8T6-TR")]
    async with client_returning({"components": rows}) as c:
        listings = await LcscAdapter(c).lookup_mpn("STM32F103C8T6")

    assert {r.mpn for r in listings} == {"STM32F103C8T6", "STM32F103C8T6-TR"}


async def test_lookup_sku_finds_the_part_and_returns_none_for_a_miss():
    async with client_returning({"components": [ROW]}) as c:
        adapter = LcscAdapter(c)
        found = await adapter.lookup_sku("C8734")
        assert found is not None and found.sku == "C8734"

        assert await adapter.lookup_sku("C99999999") is None
        assert await adapter.lookup_sku("not-a-code") is None


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


async def test_search_carries_the_lcsc_flags():
    """Both flags are native jlcsearch fields, present in search payloads,
    so they cost no extra call. Verified in docs/api-samples/search-stm32f103.json."""
    row = dict(ROW, is_basic=False, is_preferred=True)
    async with client_returning({"components": [row]}) as c:
        r = (await LcscAdapter(c).search("stm32", limit=20))[0]

    assert r.is_basic is False
    assert r.is_preferred is True


async def test_adapter_is_parametric_capable():
    async with client_returning({"components": []}) as c:
        assert isinstance(LcscAdapter(c), ParametricCapable)


async def test_list_category_returns_raw_rows_and_sends_params():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"leds": [{"lcsc": 1, "mfr": "X"}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler),
                                 base_url="https://jlcsearch.test") as c:
        rows = await LcscAdapter(c).list_category(
            "/leds/list.json", "leds", {"color": "red", "limit": 100})

    assert rows == [{"lcsc": 1, "mfr": "X"}]
    assert seen[0].url.path == "/leds/list.json"
    assert seen[0].url.params["color"] == "red"
    assert seen[0].url.params["limit"] == "100"


async def test_list_category_raises_on_a_missing_envelope():
    async with client_returning({"nope": []}) as c:
        with pytest.raises(UpstreamError):
            await LcscAdapter(c).list_category("/leds/list.json", "leds", {})


JUNK = {"lcsc": 45359915, "mfr": "CGA0402C0G9R0B500GT", "package": "0402",
        "description": "9pF 50V C0G Multilayer Ceramic Capacitors", "stock": 5,
        "price": 0.01, "is_basic": False, "is_preferred": False}


async def test_search_drops_rows_that_share_nothing_with_the_query():
    """jlcsearch rebuilt its table without its text index, so a search for an
    MCU came back as capacitors. A row naming none of the query's words in
    its MPN, package or description is not a result for that query."""
    async with client_returning({"components": [JUNK, ROW]}) as c:
        out = await LcscAdapter(c).search("STM32F103C8T6", limit=20)
    assert [r.mpn for r in out] == ["STM32F103C8T6"]


async def test_one_matching_word_is_enough_to_keep_a_row():
    """Upstream also matches category and manufacturer text we never see, so
    the check stays loose: any one word, case and punctuation ignored."""
    row = dict(ROW, mfr="RC0805FR-0710KL", package="0805",
               description="10kOhm 1% 125mW Thick Film Resistor")
    async with client_returning({"components": [row]}) as c:
        out = await LcscAdapter(c).search("yageo 10k", limit=20)
    assert len(out) == 1


async def test_a_search_answered_only_with_unrelated_parts_is_unavailable():
    """Reporting ok with nothing would hide the outage behind no results."""
    async with client_returning({"components": [JUNK]}) as c:
        with pytest.raises(UpstreamError) as exc:
            await LcscAdapter(c).search("STM32F103C8T6", limit=20)
    assert exc.value.kind == "unavailable"
    assert "unrelated" in str(exc.value)


async def test_an_honestly_empty_search_is_still_just_empty():
    async with client_returning({"components": []}) as c:
        assert await LcscAdapter(c).search("NOTAPART", limit=20) == []


async def test_lookup_mpn_is_not_filtered():
    """The detail path picks the exact part itself, and failing it here would
    turn a held row the user just saw into an error page."""
    async with client_returning({"components": [JUNK]}) as c:
        out = await LcscAdapter(c).lookup_mpn("STM32F103C8T6")
    assert [r.mpn for r in out] == ["CGA0402C0G9R0B500GT"]
