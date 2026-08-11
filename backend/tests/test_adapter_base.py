import inspect
from datetime import datetime, timezone

import pytest

from services.adapters.base import (DistributorAdapter, ParametricCapable,
                                    RawListing)

T = datetime(2026, 8, 8, 9, 14, tzinfo=timezone.utc)


def test_raw_listing_holds_a_full_listing():
    r = RawListing(distributor="lcsc", sku="C8734", mpn="STM32F103C8T6",
                   brand=None, package="LQFP-48", description="",
                   stock=12400, in_stock=True, price=1.82, currency="USD",
                   price_breaks=None, datasheet_url=None,
                   product_url=None, as_of=T)
    assert r.sku == "C8734" and r.currency == "USD"


def test_adapter_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        DistributorAdapter()


def test_adapter_requires_both_methods():
    class Half(DistributorAdapter):
        name = "half"

        async def search(self, query, limit):
            return []

    with pytest.raises(TypeError):
        Half()


def test_a_complete_adapter_instantiates():
    class Full(DistributorAdapter):
        name = "full"

        async def search(self, query, limit):
            return []

        async def lookup_mpn(self, mpn):
            return []

    assert Full().name == "full"


def test_parametric_capable_is_a_runtime_checkable_protocol():
    class NotParametric:
        pass

    class IsParametric:
        async def list_parametric(self, category, package, resistance_ohms=None):
            return []

    assert not isinstance(NotParametric(), ParametricCapable)
    assert isinstance(IsParametric(), ParametricCapable)


def test_search_and_lookup_are_coroutines():
    assert inspect.iscoroutinefunction(DistributorAdapter.search)
    assert inspect.iscoroutinefunction(DistributorAdapter.lookup_mpn)
