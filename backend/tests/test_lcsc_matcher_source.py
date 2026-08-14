"""The shim that lets the untouched v1 matcher run on LcscAdapter."""

import httpx
import pytest

from services.adapters.lcsc import LcscAdapter
from services.lcsc_matcher_source import LcscMatcherSource

pytestmark = pytest.mark.anyio

ROW = {"lcsc": 8734, "mfr": "STM32F103C8T6", "package": "LQFP-48",
       "description": "ARM MCU", "stock": 12400, "price": 1.8234,
       "is_basic": False, "is_preferred": True}
RES = {"lcsc": 100, "mfr": "R-orig", "package": "0603", "description": "",
       "stock": 1000, "price": 0.001, "price1": 0.001, "in_stock": True,
       "resistance": 10000, "tolerance_fraction": 0.01, "power_watts": 100}


def handler(request):
    if request.url.path == "/resistors/list.json":
        return httpx.Response(200, json={"resistors": [RES]})
    return httpx.Response(200, json={"components": [ROW]})


@pytest.fixture
def source():
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler),
                               base_url="https://jlcsearch.test")
    return LcscMatcherSource(LcscAdapter(client))


async def test_get_part_maps_a_listing_to_the_matcher_s_shape(source):
    detail = await source.get_part("C8734")

    assert detail.lcsc == "C8734"
    assert detail.mpn == "STM32F103C8T6"
    assert detail.package == "LQFP-48"


async def test_get_part_returns_none_for_an_unknown_code(source):
    assert await source.get_part("C99999999") is None


async def test_the_lcsc_flags_reach_the_matcher(source):
    """The matcher reads is_basic when it explains a match, so the flags
    have to survive the hop from listing to detail."""
    detail = await source.get_part("C8734")

    assert detail.is_basic is False and detail.is_preferred is True


async def test_list_parametric_passes_straight_through(source):
    parts = await source.list_parametric("resistors", "0603")

    assert [p.lcsc for p in parts] == ["C100"]
