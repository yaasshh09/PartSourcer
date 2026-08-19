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


async def test_a_held_row_stays_findable_when_upstream_renames_the_part(store):
    """Upstream can hand back a different mfr for the same sku. The kept row
    keeps its own identity, but it still has to be filed where the merge that
    just ran will look for it, or the offer vanishes on the next read."""
    first = VaryingAdapter({"q": 0.0039}, ["OLD-NAME"])
    cached = build(store, {"lcsc": first})
    await cached.search("q", 1)

    renamed = VaryingAdapter({"NEW-NAME": 0.0009}, ["NEW-NAME"])
    cached2 = build(store, {"lcsc": renamed})
    part, _, _ = await cached2.lookup("NEW-NAME")

    assert part is not None
    assert price(part) == 0.0039, "the held row still supplies the numbers"

    again, _, _ = await cached2.lookup("NEW-NAME")
    assert again is not None, "and it is still findable on the next read"
    assert price(again) == 0.0039


async def test_two_different_searches_agree_about_the_same_part(store):
    """Upstream answers by query, so two searches that both surface a part
    would otherwise price it differently in the same minute."""
    adapter = VaryingAdapter({"cheap query": 0.0039, "other query": 0.0009},
                             ["PART-A"])
    cached = build(store, {"lcsc": adapter})

    first = await cached.search("cheap query", 1)
    second = await cached.search("other query", 1)

    assert price(first.results[0]) == 0.0039
    assert price(second.results[0]) == 0.0039, "the second search re-priced it"


async def test_a_held_row_keeps_its_own_timestamp(store):
    """as_of is when those numbers were read. Stamping a held row with now
    would claim a freshness we did not earn, and would let a row live past
    its TTL by being looked at."""
    _adapter, cached = varying(store)
    found = await cached.search("1k resistor", 1)
    before = found.results[0].offers[0].as_of

    part, _, _ = await cached.lookup("PART-A")

    assert part.offers[0].as_of == before


class NoSkuAdapter(DistributorAdapter):
    """A distributor that publishes no part number, which Mouser does: it
    sends the literal "N/A" and the adapter reads that as absent."""

    name = "mouser"

    def __init__(self, priced):
        self._priced = priced          # mpn -> price
        self.queries = []

    async def search(self, query, limit):
        self.queries.append(query)
        return [RawListing(distributor="mouser", sku="", mpn=m, brand=None,
                           package="P", description="d", stock=5000,
                           in_stock=True, price=p, currency="USD",
                           price_breaks=None, datasheet_url=None,
                           product_url=None, as_of=T0, rank=i)
                for i, (m, p) in enumerate(self._priced.items())]

    async def lookup_mpn(self, mpn, limit=20):
        return await self.search(mpn, limit)


async def test_offers_with_no_sku_never_borrow_each_other_s_price(store):
    """Every no-SKU offer shares the key ("mouser", ""), so keying the hold
    on it alone hands one part whatever unrelated row came back last. A
    fabricated price with an honest timestamp is the worst failure here."""
    adapter = NoSkuAdapter({"PART-A": 1.0, "PART-B": 2.0})
    cached = build(store, {"mouser": adapter})

    await cached.search("both", 1)
    again = await cached.search("both", 1)

    by_key = {p.mpn_key: p.offers[0].price_usd for p in again.results}
    assert by_key == {"PART-A": 1.0, "PART-B": 2.0}


async def test_a_no_sku_offer_takes_the_freshly_fetched_numbers(store):
    """A second query for the same part is a miss, so it fetches and then
    looks for a row to hold. There is nothing it can safely identify, so the
    new read stands rather than a guess drawn from a shared key."""
    adapter = NoSkuAdapter({"PART-A": 1.0})
    cached = build(store, {"mouser": adapter})
    await cached.search("one", 1)

    adapter._priced = {"PART-A": 3.0}
    second = await cached.search("a different query", 1)

    assert second.results[0].offers[0].price_usd == 3.0


async def test_the_index_row_ages_from_its_oldest_held_read(store):
    """Otherwise a later query touching the same parts restarts the clock,
    and offers get served at close to twice the TTL behind a row that still
    looks fresh."""
    from datetime import timedelta
    late = T0 + timedelta(seconds=int(TTL * 0.9))
    adapter = VaryingAdapter({"first": 0.0039, "second": 0.0009}, ["PART-A"])

    at_t0 = build(store, {"lcsc": adapter}, now=lambda: T0)
    await at_t0.search("first", 1)

    later = build(store, {"lcsc": adapter}, now=lambda: late)
    await later.search("second", 1)

    row = await store.get_search("second")
    assert row.as_of == T0, "the new row claimed the numbers were read now"


async def test_held_offers_do_not_outlive_the_ttl_by_being_looked_at(store):
    from datetime import timedelta
    adapter = VaryingAdapter({"first": 0.0039, "second": 0.0009}, ["PART-A"])
    late = T0 + timedelta(seconds=int(TTL * 0.9))
    past = T0 + timedelta(seconds=int(TTL * 1.5))

    await build(store, {"lcsc": adapter}, now=lambda: T0).search("first", 1)
    await build(store, {"lcsc": adapter}, now=lambda: late).search("second", 1)

    adapter._as_of = past
    after = build(store, {"lcsc": adapter}, now=lambda: past)
    result = await after.search("second", 1)

    assert price(result.results[0]) == 0.0009, "served numbers past the TTL"
