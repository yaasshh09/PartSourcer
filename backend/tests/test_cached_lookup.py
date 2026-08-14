import pytest

from tests.test_cached_search import CountingAdapter, build, store  # noqa: F401

pytestmark = pytest.mark.anyio


async def test_a_lookup_hit_makes_no_second_call(store):
    lcsc = CountingAdapter("lcsc", ["PART-A"])
    cached = build(store, {"lcsc": lcsc})

    await cached.lookup("PART-A")
    part, sources, canonical = await cached.lookup("PART-A")

    assert lcsc.calls == 1
    assert canonical is True and part.mpn_key == "PART-A"


async def test_a_distributor_that_carries_nothing_is_not_re_asked(store):
    """Without part_cache, every request for a part LCSC does not stock
    would call LCSC forever, because absence looks identical to never asked."""
    empty = CountingAdapter("lcsc", [])
    cached = build(store, {"lcsc": empty})

    await cached.lookup("PART-A")
    part, _, _ = await cached.lookup("PART-A")

    assert empty.calls == 1
    assert part is None


async def test_fold_drift_asks_for_a_redirect_rather_than_404(store):
    lcsc = CountingAdapter("lcsc", ["PART-A", "PART-A-TR"])
    cached = build(store, {"lcsc": lcsc})

    part, _, canonical = await cached.lookup("PART-A-TR")

    assert canonical is False and part.mpn_key == "PART-A"


async def test_only_the_requested_key_gets_a_status_row(store):
    """A keyword lookup drags in other parts. Their offers are free cache
    warming, but claiming we asked about them would be a lie."""
    lcsc = CountingAdapter("lcsc", ["PART-A", "PART-OTHER"])
    cached = build(store, {"lcsc": lcsc})

    await cached.lookup("PART-A")

    assert await store.get_part_status("PART-A") is not None
    assert await store.get_part_status("PART-OTHER") is None


async def test_resolve_sku_finds_the_part_key_from_a_warmed_cache(store):
    lcsc = CountingAdapter("lcsc", ["PART-A"])
    cached = build(store, {"lcsc": lcsc})
    await cached.lookup("PART-A")

    assert await cached.resolve_sku("lcsc", "L0") == "PART-A"
    assert await cached.resolve_sku("lcsc", "NOPE") is None
