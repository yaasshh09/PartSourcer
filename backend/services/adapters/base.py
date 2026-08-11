"""One adapter per distributor.

An adapter knows its own API and nothing else: no merging, no caching, no
awareness that other distributors exist. PartService owns all of that.

list_parametric is deliberately NOT on the ABC. Mouser and DigiKey have
parametric search, but their taxonomies bear no resemblance to
jlcsearch's /resistors/list.json, so requiring it would force two adapters
to fake a method. It is a capability instead, and only LcscAdapter has it.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from models.parametric import ParametricPart
from services.datasource import UPSTREAM_STATUS, UpstreamError  # noqa: F401

__all__ = ["RawListing", "DistributorAdapter", "ParametricCapable",
           "UpstreamError", "UPSTREAM_STATUS"]


@dataclass
class RawListing:
    """One distributor's listing, before any cross-distributor merging."""
    distributor: str
    sku: str
    mpn: str
    brand: str | None
    package: str
    description: str
    stock: int
    in_stock: bool
    price: float
    currency: str
    price_breaks: list[dict] | None
    datasheet_url: str | None
    product_url: str | None
    as_of: datetime


class DistributorAdapter(ABC):
    name: str

    @abstractmethod
    async def search(self, query: str, limit: int) -> list[RawListing]: ...

    @abstractmethod
    async def lookup_mpn(self, mpn: str) -> list[RawListing]: ...


@runtime_checkable
class ParametricCapable(Protocol):
    async def list_parametric(self, category: str, package: str,
                              resistance_ohms: float | None = None
                              ) -> list[ParametricPart]: ...
