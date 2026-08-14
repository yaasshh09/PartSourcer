from datetime import datetime, timezone

from cache.serde import listing_from_dict, listing_to_dict
from services.adapters.base import RawListing


def make_listing() -> RawListing:
    return RawListing(
        distributor="mouser", sku="511-STM32", mpn="STM32F103C8T6",
        brand="STMicroelectronics", package="LQFP-48", description="MCU",
        stock=3150, in_stock=True, price=2.94, currency="USD",
        price_breaks=[{"qty": 1, "price_usd": 2.94}],
        datasheet_url="https://example.invalid/ds.pdf",
        product_url="https://example.invalid/p", is_basic=None,
        is_preferred=None, rank=3,
        as_of=datetime(2026, 8, 14, 9, 14, tzinfo=timezone.utc))


def test_round_trip_is_lossless():
    """The whole cache design rests on this: a listing read back must be the
    listing that went in, so merge over cached rows equals merge over live."""
    original = make_listing()

    assert listing_from_dict(listing_to_dict(original)) == original


def test_serialized_form_is_json_safe():
    import json

    assert json.dumps(listing_to_dict(make_listing()))
