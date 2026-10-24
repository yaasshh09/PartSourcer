"""GET /api/feed/{mpn_key}: an RSS feed of the changes worth hearing about.

A feed reader is the alert for people who would rather not hand over an
email, so an item has to mean something: a price move or the part going out
of or back into stock. A nightly stock wobble is not news.
"""

import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

import services.deps as deps
from history.store import InMemoryHistoryStore, OfferRecord
from main import app


def teardown_function():
    app.dependency_overrides.clear()


def row(days_ago, price, stock=100):
    return OfferRecord(
        mpn_key="STM32F103C8T6", lcsc="C8734", distributor="lcsc", sku="C8734",
        price_usd=price, stock=stock, in_stock=stock > 0, currency="USD",
        recorded_at=datetime.now(timezone.utc) - timedelta(days=days_ago))


def get(store, path="/api/feed/stm32f103c8t6"):
    app.dependency_overrides[deps.get_history_store] = lambda: store
    return TestClient(app).get(path)


def titles(resp):
    return [i.findtext("title") for i in ET.fromstring(resp.text).iter("item")]


def test_only_price_moves_and_stock_flips_become_items_newest_first():
    store = InMemoryHistoryStore()
    store.records = [row(6, 1.82, 1200), row(5, 1.82, 1100), row(4, 1.75, 1000),
                     row(3, 1.75, 0), row(2, 1.75, 0), row(1, 1.75, 900)]
    resp = get(store)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/rss+xml")
    assert titles(resp) == [
        "STM32F103C8T6 back in stock: 900 at LCSC",
        "STM32F103C8T6 out of stock at LCSC",
        "STM32F103C8T6 price went from $1.82 to $1.75 at LCSC",
        "STM32F103C8T6 first reading: $1.82, 1,200 in stock at LCSC",
    ]
    channel = ET.fromstring(resp.text).find("channel")
    assert channel.findtext("link").endswith("/part/STM32F103C8T6")
    assert "snapshot" in channel.findtext("description")
    assert "live" not in channel.findtext("description").lower()


def test_items_have_stable_guids_and_dates():
    store = InMemoryHistoryStore()
    store.records = [row(2, 0.004), row(1, 0.003)]
    items = list(ET.fromstring(get(store).text).iter("item"))
    assert items[0].findtext("title") == "STM32F103C8T6 price went from $0.0040 to $0.0030 at LCSC"
    guids = [i.findtext("guid") for i in items]
    assert len(set(guids)) == 2
    assert all(i.findtext("pubDate").endswith("+0000") for i in items)
    assert guids == [i.findtext("guid") for i in ET.fromstring(get(store).text).iter("item")]


def test_a_part_with_no_rows_is_an_empty_feed_not_an_error():
    resp = get(InMemoryHistoryStore())
    assert resp.status_code == 200 and titles(resp) == []


def test_no_store_is_a_404():
    assert get(None).status_code == 404


def test_markup_in_the_key_is_escaped():
    resp = get(InMemoryHistoryStore(), "/api/feed/A<B>&C")
    assert resp.status_code == 200
    ET.fromstring(resp.text)    # parses, so nothing leaked through unescaped
