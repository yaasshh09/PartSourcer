"""The shim that lets the untouched v1 matcher run on LcscAdapter."""

import httpx
import pytest

from services.adapters.lcsc import LcscAdapter
from services.lcsc_matcher_source import LcscMatcherSource
from services.part_service import FETCH_DEPTH

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


# --- canonical_part -----------------------------------------------------
# Upstream answers differently depending on how a part is asked for, so the
# matcher publishes only what this read returns: the same call, at the same
# depth, that fills the offer cache behind the search and detail pages.


def recording_handler(seen):
    def handler(request):
        if request.url.path == "/resistors/list.json":
            return httpx.Response(200, json={"resistors": [RES]})
        seen.append(dict(request.url.params))
        return httpx.Response(200, json={"components": [ROW]})
    return handler


def source_over(handler):
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler),
                               base_url="https://jlcsearch.test")
    return LcscMatcherSource(LcscAdapter(client))


async def test_canonical_part_returns_the_row_for_that_code(source):
    detail = await source.canonical_part("STM32F103C8T6", "C8734")

    assert detail.lcsc == "C8734"
    assert detail.price_usd == 1.8234
    assert detail.stock == 12400


async def test_canonical_part_is_none_when_the_code_is_not_in_the_answer():
    """A part can be missing at this depth even though the code is real. No
    row means no confirmed price, which the matcher reports honestly rather
    than falling back to the other read."""
    detail = await source_over(recording_handler([])).canonical_part(
        "SOME-OTHER-MPN", "C99999999")

    assert detail is None


async def test_canonical_part_reads_at_the_shared_fetch_depth():
    seen = []
    await source_over(recording_handler(seen)).canonical_part(
        "STM32F103C8T6", "C8734")

    assert seen == [{"q": "STM32F103C8T6", "limit": str(FETCH_DEPTH)}]


# --- canonical_part reads through the offer cache ------------------------
# The pages serve one cached row per offer and hold it until it expires, so
# a second upstream read here would be a second answer for the same part.


@pytest.fixture
def cache_store(tmp_path):
    from cache.store import SqliteCacheStore
    s = SqliteCacheStore(str(tmp_path / "c.db"))
    s.open()
    yield s
    s.close()


async def _seed(store, price, as_of):
    from cache.serde import listing_to_dict
    from cache.store import CachedOffer
    from services.adapters.base import RawListing
    listing = RawListing(distributor="lcsc", sku="C8734",
                         mpn="STM32F103C8T6", brand=None, package="LQFP-48",
                         description="", stock=999, in_stock=True,
                         price=price, currency="USD", price_breaks=None,
                         datasheet_url=None, product_url=None, as_of=as_of,
                         rank=0)
    await store.put_offers([CachedOffer(
        listing_key="STM32F103C8T6", distributor="lcsc", sku="C8734",
        part_key="STM32F103C8T6", listing=listing_to_dict(listing),
        as_of=as_of)])


async def test_canonical_part_serves_the_cached_row(cache_store):
    from datetime import datetime, timezone
    now = datetime(2026, 8, 19, tzinfo=timezone.utc)
    await _seed(cache_store, 0.0039, now)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler),
                               base_url="https://jlcsearch.test")
    source = LcscMatcherSource(LcscAdapter(client), store=cache_store,
                               offer_ttl_secs=3600, now=lambda: now)

    detail = await source.canonical_part("STM32F103C8T6", "C8734")

    # 1.8234 is what the mock upstream would say; the held row wins.
    assert detail.price_usd == 0.0039
    assert detail.stock == 999


async def test_canonical_part_reads_upstream_when_the_row_is_stale(cache_store):
    from datetime import datetime, timedelta, timezone
    then = datetime(2026, 8, 19, tzinfo=timezone.utc)
    await _seed(cache_store, 0.0039, then)
    later = then + timedelta(seconds=7200)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler),
                               base_url="https://jlcsearch.test")
    source = LcscMatcherSource(LcscAdapter(client), store=cache_store,
                               offer_ttl_secs=3600, now=lambda: later)

    detail = await source.canonical_part("STM32F103C8T6", "C8734")

    assert detail.price_usd == 1.8234


async def test_canonical_part_keeps_what_it_just_quoted(cache_store):
    """A candidate priced for an equivalent card has no row yet. Without
    keeping it, following the card could land on a different number."""
    from datetime import datetime, timezone
    now = datetime(2026, 8, 19, tzinfo=timezone.utc)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler),
                               base_url="https://jlcsearch.test")
    source = LcscMatcherSource(LcscAdapter(client), store=cache_store,
                               offer_ttl_secs=3600, now=lambda: now)

    quoted = await source.canonical_part("STM32F103C8T6", "C8734")
    rows = await cache_store.get_offers_by_sku([("lcsc", "C8734")])

    assert quoted.price_usd == 1.8234
    assert len(rows) == 1
    assert rows[0].part_key == "STM32F103C8T6"


async def test_remembering_never_displaces_a_live_row(cache_store):
    from datetime import datetime, timezone
    now = datetime(2026, 8, 19, tzinfo=timezone.utc)
    await _seed(cache_store, 0.0039, now)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler),
                               base_url="https://jlcsearch.test")
    source = LcscMatcherSource(LcscAdapter(client), store=cache_store,
                               offer_ttl_secs=3600, now=lambda: now)

    await source.canonical_part("STM32F103C8T6", "C8734")
    rows = await cache_store.get_offers_by_sku([("lcsc", "C8734")])

    from cache.serde import listing_from_dict as lfd
    assert lfd(rows[0].listing).price == 0.0039
