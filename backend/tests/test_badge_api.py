"""GET /api/badge/{mpn_key}: an SVG for project READMEs.

Every state answers 200 with an SVG, because a README shows a broken image
for anything else. The read date is always on it, because the image gets
cached by whoever embeds it.
"""

from fastapi.testclient import TestClient

import services.deps as deps
from main import app
from models.offer import Cheapest
from services.datasource import UpstreamError
from tests.stub_cached import StubCached, StubLcsc, offer, part


def teardown_function():
    app.dependency_overrides.clear()


def get(cached, path="/api/badge/STM32F103C8T6"):
    app.dependency_overrides[deps.get_cached_service] = lambda: cached
    app.dependency_overrides[deps.get_lcsc_adapter] = lambda: StubLcsc()
    return TestClient(app).get(path)


def test_shows_stock_across_distributors_and_the_read_date():
    p = part(offers=[offer(), offer(distributor="mouser", sku="M-1")])
    resp = get(StubCached(found=p))
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/svg+xml")
    assert "429,192 in stock" in resp.text
    assert "Aug 14" in resp.text
    assert "max-age=3600" in resp.headers["cache-control"]


def test_a_price_only_when_the_backend_named_a_cheapest():
    assert "$" not in get(StubCached(found=part())).text
    p = part()
    p.cheapest = Cheapest(distributor="lcsc", sku="C8734", price_usd=1.04,
                          compared_sources=2, of_sources=3)
    assert "from $1.04" in get(StubCached(found=p)).text


def test_packaging_variants_and_empty_shelves_do_not_count():
    reel = offer(sku="C9", tier="packaging")
    empty = offer(distributor="mouser", sku="M-2")
    empty.stock, empty.in_stock = 0, False
    assert "214,596 in stock" in get(StubCached(found=part(offers=[offer(), reel, empty]))).text
    out = offer()
    out.stock, out.in_stock = 0, False
    assert "out of stock" in get(StubCached(found=part(offers=[out]))).text


def test_not_found_and_upstream_trouble_still_draw_a_badge():
    missing = get(StubCached(found=None))
    assert missing.status_code == 200 and "not found" in missing.text
    down = get(StubCached(error=UpstreamError("timeout", "slow")))
    assert down.status_code == 200 and "unavailable" in down.text
    assert "max-age=300" in down.headers["cache-control"]
