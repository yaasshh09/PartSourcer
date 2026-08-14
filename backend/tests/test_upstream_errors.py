"""How a jlcsearch failure becomes an UpstreamError.

Carried over from the deleted v1 datasource tests. Same assertions, aimed at
LcscAdapter._fetch_json, which is the one place that speaks jlcsearch now.
"""

import httpx
import pytest

from services.adapters.base import UpstreamError
from services.adapters.lcsc import LcscAdapter

pytestmark = pytest.mark.anyio


def adapter_over(handler):
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler),
                               base_url="https://jlcsearch.test")
    return LcscAdapter(client)


async def test_timeout_raises_upstream_error():
    def handler(request):
        raise httpx.ConnectTimeout("boom")

    with pytest.raises(UpstreamError) as ei:
        await adapter_over(handler).search("stm32", limit=20)

    assert ei.value.kind == "timeout"


async def test_transport_error_raises_unavailable():
    def handler(request):
        raise httpx.ConnectError("no route")

    with pytest.raises(UpstreamError) as ei:
        await adapter_over(handler).search("stm32", limit=20)

    assert ei.value.kind == "unavailable"


async def test_upstream_500_raises_unavailable():
    with pytest.raises(UpstreamError) as ei:
        await adapter_over(lambda req: httpx.Response(500, text="oops")) \
            .search("stm32", limit=20)

    assert ei.value.kind == "unavailable"


async def test_malformed_body_raises_unavailable():
    handler = lambda req: httpx.Response(200, text="<html>not json</html>")  # noqa: E731

    with pytest.raises(UpstreamError) as ei:
        await adapter_over(handler).search("stm32", limit=20)

    assert ei.value.kind == "unavailable"


async def test_non_dict_json_body_raises_unavailable():
    with pytest.raises(UpstreamError) as ei:
        await adapter_over(lambda req: httpx.Response(200, json=[1, 2, 3])) \
            .search("stm32", limit=20)

    assert ei.value.kind == "unavailable"


async def test_a_missing_list_key_raises_unavailable():
    with pytest.raises(UpstreamError) as ei:
        await adapter_over(lambda req: httpx.Response(200, json={"wrong": []})) \
            .search("stm32", limit=20)

    assert ei.value.kind == "unavailable"


async def test_list_parametric_maps_the_same_failures():
    def handler(request):
        raise httpx.ConnectTimeout("boom")

    with pytest.raises(UpstreamError) as ei:
        await adapter_over(handler).list_parametric("resistors", "0603")

    assert ei.value.kind == "timeout"


async def test_list_parametric_missing_envelope_raises():
    with pytest.raises(UpstreamError):
        await adapter_over(lambda req: httpx.Response(200, json={"wrong": []})) \
            .list_parametric("resistors", "0603")
