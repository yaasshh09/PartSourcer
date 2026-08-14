"""Cache decisions are observable, and never at the cost of a leak."""

import logging

import pytest

from tests.test_cached_search import CountingAdapter, build, store  # noqa: F401

pytestmark = pytest.mark.anyio


async def test_a_search_logs_its_cache_decision(store, caplog):
    lcsc = CountingAdapter("lcsc", ["PART-A"])
    cached = build(store, {"lcsc": lcsc})

    with caplog.at_level(logging.INFO, logger="partsourcer.cache"):
        await cached.search("stm32", 1)
        await cached.search("stm32", 1)

    messages = [r.getMessage() for r in caplog.records]
    assert any("miss" in m for m in messages)
    assert any("hit" in m for m in messages)


async def test_a_lookup_logs_its_cache_decision(store, caplog):
    lcsc = CountingAdapter("lcsc", ["PART-A"])
    cached = build(store, {"lcsc": lcsc})

    with caplog.at_level(logging.INFO, logger="partsourcer.cache"):
        await cached.lookup("PART-A")
        await cached.lookup("PART-A")

    messages = [r.getMessage() for r in caplog.records]
    assert any("lookup miss" in m for m in messages)
    assert any("lookup hit" in m for m in messages)


async def test_every_source_outcome_is_logged(store, caplog):
    lcsc = CountingAdapter("lcsc", ["PART-A"])
    cached = build(store, {"lcsc": lcsc})

    with caplog.at_level(logging.INFO, logger="partsourcer.cache"):
        await cached.search("stm32", 1)

    assert any("source=lcsc state=ok" in r.getMessage() for r in caplog.records)


async def test_a_failure_logs_the_type_not_the_message(store, caplog):
    """The Mouser key rides in a query string and httpx puts request URLs in
    exception messages, so a logged message is a leak waiting to happen."""
    broken = CountingAdapter("mouser", [], fail="unavailable")
    broken._secret = "apiKey=hunter2"
    cached = build(store, {"mouser": broken})

    with caplog.at_level(logging.INFO, logger="partsourcer.cache"):
        await cached.search("stm32", 1)

    assert not any("hunter2" in r.getMessage() for r in caplog.records)
