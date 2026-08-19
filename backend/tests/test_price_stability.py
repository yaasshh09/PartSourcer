"""One cached offer row is one answer until it expires.

Upstream returns different prices for the same part depending on how it is
asked, and our two surfaces ask differently: search sends the user's words,
the detail page sends the MPN. Measured against live upstream, about a
quarter of search cards disagreed with their own part page, by up to 4x.
Letting the later read win meant the number a user was already looking at
changed on click-through, both readings honestly timestamped.
"""

from datetime import timedelta

import pytest

from cache.serde import listing_from_dict
from services.adapters.base import DistributorAdapter, RawListing
from tests.test_cached_search import T0, TTL, build, store  # noqa: F401

pytestmark = pytest.mark.anyio


class VaryingAdapter(DistributorAdapter):
    """Answers differently depending on the query, exactly as upstream does."""

    name = "lcsc"

    def __init__(self, by_query, mpns, as_of=T0, default=9.99):
        self._by_query = by_query
        self._mpns = mpns
        self._as_of = as_of
        self._default = default
        self.queries = []

    async def search(self, query, limit):
        self.queries.append(query)
        price = self._by_query.get(query, self._default)
        return [RawListing(distributor="lcsc", sku=f"L{i}", mpn=m, brand=None,
                           package="P", description="d", stock=100,
                           in_stock=True, price=price, currency="USD",
                           price_breaks=None, datasheet_url=None,
                           product_url=None, as_of=self._as_of, rank=i)
                for i, m in enumerate(self._mpns[:limit])]

    async def lookup_mpn(self, mpn, limit=20):
        return await self.search(mpn, limit)


def varying(store_, as_of=T0, now=None):   # noqa: F811
    adapter = VaryingAdapter({"1k resistor": 0.0039, "PART-A": 0.0009},
                             ["PART-A"], as_of=as_of)
    return adapter, build(store_, {"lcsc": adapter},
                          now=now or (lambda: T0))


def price(part):
    return part.offers[0].price_usd


async def test_a_search_price_survives_the_click_through(store):
    adapter, cached = varying(store)

    found = await cached.search("1k resistor", 1)
    assert price(found.results[0]) == 0.0039

    part, _, _ = await cached.lookup("PART-A")

    assert price(part) == 0.0039, "the price moved when the user clicked"
    assert "PART-A" in adapter.queries, "the detail read still happened"


async def test_the_store_holds_exactly_what_was_shown(store):
    """The response and the row must not diverge, or the next read flips
    back and the number oscillates."""
    _adapter, cached = varying(store)
    await cached.search("1k resistor", 1)
    await cached.lookup("PART-A")

    rows = await store.get_offers_by_sku([("lcsc", "L0")])

    assert listing_from_dict(rows[0].listing).price == 0.0039


async def test_going_back_to_the_search_shows_the_same_number(store):
    _adapter, cached = varying(store)
    first = await cached.search("1k resistor", 1)
    await cached.lookup("PART-A")
    again = await cached.search("1k resistor", 1)

    assert price(again.results[0]) == price(first.results[0]) == 0.0039


async def test_an_explicit_refresh_does_replace_it(store):
    """Holding a row is not the same as refusing to update. Asking for fresh
    data has to actually get it."""
    _adapter, cached = varying(store)
    await cached.search("1k resistor", 1)

    part, _, _ = await cached.lookup("PART-A", refresh=True)

    assert price(part) == 0.0009


async def test_a_row_past_its_ttl_is_replaced(store):
    later = T0 + timedelta(seconds=TTL + 1)
    _adapter, cached = varying(store)
    await cached.search("1k resistor", 1)

    # Same store, a clock past the TTL, so the held row is no longer fresh.
    _later_adapter, after_ttl = varying(store, as_of=later, now=lambda: later)
    part, _, _ = await after_ttl.lookup("PART-A")

    assert price(part) == 0.0009


async def test_a_part_with_no_row_yet_takes_the_new_read(store):
    _adapter, cached = varying(store)

    part, _, _ = await cached.lookup("PART-A")

    assert price(part) == 0.0009
