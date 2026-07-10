"""Internal parametric-candidate model (not a response shape).

One row from a jlcsearch parametric endpoint (/resistors, /capacitors),
mapped to a datasource-neutral shape. `specs` carries the type-specific
fields the matcher reasons over (resistance, capacitance_farads, ...).
"""

from pydantic import BaseModel


class ParametricPart(BaseModel):
    lcsc: str
    mpn: str
    package: str
    stock: int
    price_usd: float
    in_stock: bool
    is_basic: bool | None = None
    is_preferred: bool | None = None
    specs: dict
