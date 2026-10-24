"""Link previews: a PNG card per part, and a share page that carries it.

Social sites cache a preview for a long time, so the card always prints the
moment its numbers were read, and every failure still answers with an image.
"""

import io

from fastapi.testclient import TestClient
from PIL import Image

import services.deps as deps
from api.share import headline, summary
from main import app
from services.datasource import UpstreamError
from tests.stub_cached import StubCached, StubLcsc, offer, part


def teardown_function():
    app.dependency_overrides.clear()


def get(cached, path):
    app.dependency_overrides[deps.get_cached_service] = lambda: cached
    app.dependency_overrides[deps.get_lcsc_adapter] = lambda: StubLcsc()
    return TestClient(app).get(path, follow_redirects=False)


def test_the_card_is_a_1200_by_630_png_that_caches_for_the_offer_ttl():
    resp = get(StubCached(found=part()), "/api/og/part/STM32F103C8T6")
    assert resp.status_code == 200 and resp.headers["content-type"] == "image/png"
    assert Image.open(io.BytesIO(resp.content)).size == (1200, 630)
    assert "max-age=3600" in resp.headers["cache-control"]


def test_a_failure_is_still_an_image_cached_briefly():
    for cached in (StubCached(error=UpstreamError("timeout", "slow")), StubCached(found=None)):
        resp = get(cached, "/api/og/part/NOPE")
        assert resp.status_code == 200 and resp.headers["content-type"] == "image/png"
        assert "max-age=300" in resp.headers["cache-control"]


def test_the_headline_is_the_one_the_part_page_shows():
    p = part(offers=[offer(distributor="mouser", sku="M", price=0.5),
                     offer(distributor="lcsc", sku="C1", price=0.8)])
    assert headline(p).distributor == "mouser"
    out = part(offers=[offer(price=None)])
    assert headline(out).price_usd is None
    assert headline(part(offers=[])) is None


def test_the_summary_names_its_distributor_and_read_date_and_never_says_cheapest():
    lines = summary(part())
    text = " ".join(lines)
    assert "$1.04 at LCSC" in text and "214,596 in stock" in text and "Aug 14, 2026" in text
    assert "cheapest" not in text.lower()
    assert "no price" in " ".join(summary(part(offers=[offer(price=None)])))


def test_the_share_page_carries_preview_tags_and_sends_people_on():
    resp = get(StubCached(found=part()), "/api/share/part/STM32F103C8T6")
    assert resp.status_code == 200 and resp.headers["content-type"].startswith("text/html")
    html = resp.text
    assert '<meta property="og:image" content="https://part-sourcer.vercel.app/api/og/part/STM32F103C8T6"' in html
    assert '<meta property="og:url" content="https://part-sourcer.vercel.app/part/STM32F103C8T6"' in html
    assert 'name="twitter:card" content="summary_large_image"' in html
    assert 'http-equiv="refresh" content="0; url=https://part-sourcer.vercel.app/part/STM32F103C8T6"' in html


def test_the_share_page_escapes_what_it_did_not_write():
    resp = get(StubCached(found=None), '/api/share/part/"><script>x</script>')
    assert "<script>x" not in resp.text
    assert resp.status_code == 200
