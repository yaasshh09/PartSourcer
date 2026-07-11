import httpx
import pytest

from models.parametric import ParametricPart
from services.datasource import JlcSearchDataSource, UpstreamError, PAGE_SIZE

RAW = {"lcsc": 8734, "mfr": "STM32F103C8T6", "package": "LQFP-48(7x7)",
       "is_basic": False, "is_preferred": True, "description": "",
       "stock": 214596, "price": 1.037142857}


def make_ds(handler):
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(
        base_url="https://jlcsearch.tscircuit.com", transport=transport)
    return JlcSearchDataSource(client)


def items_handler(items):
    def handler(request):
        return httpx.Response(200, json={"components": items})
    return handler


@pytest.mark.anyio
async def test_maps_fields():
    ds = make_ds(items_handler([RAW]))
    results = await ds.search("STM32F103", page=1)
    r = results[0]
    assert r.lcsc == "C8734"
    assert r.mpn == "STM32F103C8T6"
    assert r.brand is None and r.datasheet_url is None
    assert r.price_usd == 1.0371
    assert r.stock == 214596
    assert r.as_of is not None


@pytest.mark.anyio
async def test_pagination_windows():
    items = [dict(RAW, lcsc=i) for i in range(1, 51)]  # 50 items
    ds = make_ds(items_handler(items))
    p1 = await ds.search("x", page=1)
    p2 = await ds.search("x", page=2)
    p9 = await ds.search("x", page=9)
    assert len(p1) == PAGE_SIZE and p1[0].lcsc == "C1"
    assert len(p2) == PAGE_SIZE and p2[0].lcsc == "C21"
    assert p9 == []


@pytest.mark.anyio
async def test_empty_query_skips_upstream():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"components": []})

    ds = make_ds(handler)
    assert await ds.search("", page=1) == []
    assert await ds.search("   ", page=1) == []
    assert calls == []


@pytest.mark.anyio
async def test_timeout_raises_upstream_error():
    def handler(request):
        raise httpx.ConnectTimeout("boom")

    ds = make_ds(handler)
    with pytest.raises(UpstreamError) as ei:
        await ds.search("x", page=1)
    assert ei.value.kind == "timeout"


@pytest.mark.anyio
async def test_upstream_500_raises_unavailable():
    ds = make_ds(lambda req: httpx.Response(500, text="oops"))
    with pytest.raises(UpstreamError) as ei:
        await ds.search("x", page=1)
    assert ei.value.kind == "unavailable"


@pytest.mark.anyio
async def test_malformed_body_raises_unavailable():
    ds = make_ds(lambda req: httpx.Response(200, text="<html>not json</html>"))
    with pytest.raises(UpstreamError) as ei:
        await ds.search("x", page=1)
    assert ei.value.kind == "unavailable"


@pytest.mark.anyio
async def test_get_part_exact_match():
    def handler(request):
        assert request.url.params["q"] == "8734"
        return httpx.Response(200, json={"components": [RAW]})

    ds = make_ds(handler)
    part = await ds.get_part("C8734")
    assert part is not None and part.lcsc == "C8734"


@pytest.mark.anyio
async def test_get_part_not_found():
    ds = make_ds(items_handler([]))
    assert await ds.get_part("C000000") is None


@pytest.mark.anyio
async def test_get_part_returns_detail_with_flags():
    from models.part import PartDetail
    ds = make_ds(items_handler([RAW]))
    part = await ds.get_part("C8734")
    assert isinstance(part, PartDetail)
    assert part.lcsc == "C8734"
    assert part.is_basic is False and part.is_preferred is True
    assert part.price_breaks is None and part.stock_breakdown is None
    assert part.price_usd == 1.0371
    assert part.brand is None and part.datasheet_url is None


RES_ROW = {"lcsc": 25804, "mfr": "0603WAF1002T5E", "description": "", "stock": 37165617,
           "price1": 0.000842857, "in_stock": True, "resistance": 10000,
           "tolerance_fraction": 0.01, "power_watts": 100, "package": "0603",
           "is_basic": True, "is_preferred": False}
CAP_ROW = {"lcsc": 1525, "mfr": "CL05B104KO5NNNC", "description": "", "stock": 54323629,
           "price1": 0.001085714, "in_stock": True, "capacitance_farads": 1e-07,
           "tolerance_fraction": 0.1, "voltage_rating": 16, "package": "0402",
           "temperature_coefficient": "X7R", "is_basic": True, "is_preferred": False}


def parametric_handler(key, rows, captured=None):
    def handler(request):
        if captured is not None:
            captured["url"] = str(request.url)
        return httpx.Response(200, json={key: rows})
    return handler


@pytest.mark.anyio
async def test_list_parametric_maps_resistor():
    ds = make_ds(parametric_handler("resistors", [RES_ROW]))
    parts = await ds.list_parametric("resistors", "0603")
    assert len(parts) == 1
    p = parts[0]
    assert isinstance(p, ParametricPart)
    assert p.lcsc == "C25804"
    assert p.mpn == "0603WAF1002T5E"
    assert p.price_usd == 0.0008           # price1 rounded 4dp
    assert p.in_stock is True
    assert p.specs["resistance"] == 10000
    assert p.specs["power_watts"] == 100
    assert p.specs["tolerance_fraction"] == 0.01


@pytest.mark.anyio
async def test_list_parametric_maps_capacitor():
    ds = make_ds(parametric_handler("capacitors", [CAP_ROW]))
    parts = await ds.list_parametric("capacitors", "0402")
    p = parts[0]
    assert p.lcsc == "C1525"
    assert p.specs["capacitance_farads"] == 1e-07
    assert p.specs["voltage_rating"] == 16
    assert p.specs["temperature_coefficient"] == "X7R"


@pytest.mark.anyio
async def test_list_parametric_passes_resistance_in_raw_ohms():
    captured = {}
    ds = make_ds(parametric_handler("resistors", [RES_ROW], captured))
    await ds.list_parametric("resistors", "0603", resistance_ohms=10000)
    assert "resistance=10000" in captured["url"]
    assert "package=0603" in captured["url"]


@pytest.mark.anyio
async def test_list_parametric_timeout_raises_upstream():
    def handler(request):
        raise httpx.ConnectTimeout("boom")
    ds = make_ds(handler)
    with pytest.raises(UpstreamError) as ei:
        await ds.list_parametric("resistors", "0603")
    assert ei.value.kind == "timeout"


@pytest.mark.anyio
async def test_list_parametric_http_error_raises_unavailable():
    ds = make_ds(lambda req: httpx.Response(500, text="oops"))
    with pytest.raises(UpstreamError) as ei:
        await ds.list_parametric("resistors", "0603")
    assert ei.value.kind == "unavailable"


@pytest.mark.anyio
async def test_list_parametric_missing_envelope_raises():
    ds = make_ds(lambda req: httpx.Response(200, json={"wrong": []}))
    with pytest.raises(UpstreamError):
        await ds.list_parametric("resistors", "0603")
