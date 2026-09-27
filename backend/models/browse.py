"""Browse response shapes. There is no price field here on purpose: a
parametric price is a different basis from the part page (spec D2)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class FilterSpec(BaseModel):
    name: str
    label: str
    kind: Literal["choice", "number", "bool"]
    unit: str | None = None
    choices: list[str] | None = None
    example: str | None = None


class CategorySpec(BaseModel):
    slug: str
    label: str
    note: str | None = None
    filters: list[FilterSpec]


class CategoriesResponse(BaseModel):
    categories: list[CategorySpec]


class BrowseRow(BaseModel):
    mpn: str
    mpn_key: str
    lcsc: str
    package: str
    stock: int
    specs: list[tuple[str, str | None]]


class BrowseResponse(BaseModel):
    category: str
    results: list[BrowseRow]
    count: int
    capped: bool
    as_of: datetime
