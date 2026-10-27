"""Browse by category: the table, the query builder and the cached read.

Every category is data. Adding one is an entry in CATEGORIES plus a live
check that each choice returns rows, because upstream answers a value it does
not understand with an empty list and HTTP 200, never an error.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable
from urllib.parse import urlencode

from models.browse import (BrowseResponse, BrowseRow, CategoriesResponse,
                           CategorySpec, FilterSpec)
from services.matching import normalize_exact
from services.units import fmt_farads, fmt_ohms, fmt_si, parse_si

UPSTREAM_CAP = 100      # jlcsearch hard cap, and there is no paging


class UnknownCategory(LookupError):
    pass


class BadFilter(ValueError):
    pass


@dataclass(frozen=True)
class Filter:
    name: str
    label: str
    kind: str                   # "choice" | "number" | "bool"
    upstream: str
    unit: str | None = None
    choices: tuple[str, ...] = ()
    example: str | None = None
    # Narrows what upstream sent back, for a filter upstream applies loosely.
    refine: Callable[[dict, float], bool] | None = None


@dataclass(frozen=True)
class Column:
    label: str
    read: Callable[[dict], str | None]


@dataclass(frozen=True)
class Category:
    slug: str                   # also the upstream path and envelope key
    label: str
    filters: tuple[Filter, ...]
    columns: tuple[Column, ...]
    note: str | None = None

    @property
    def path(self) -> str:
        return f"/{self.slug}/list.json"


def _field(name: str, fmt: Callable) -> Callable[[dict], str | None]:
    def read(row: dict) -> str | None:
        value = row.get(name)
        if value is None:
            return None
        try:
            return fmt(value)
        except (TypeError, ValueError):
            return None         # unreadable upstream value: show "not listed"
    return read


def _si(unit: str) -> Callable:
    return lambda v: fmt_si(float(v), unit)


def _percent(v) -> str:
    return f"±{float(v) * 100:g}%"


def _milliwatts(v) -> str:
    return f"{float(v):g} mW"   # upstream power_watts is milliwatts, per the matcher


def _text(v) -> str | None:
    return str(v).strip() or None


def _ldo_output(row: dict) -> str | None:
    lo, hi = row.get("output_voltage_min"), row.get("output_voltage_max")
    if not isinstance(lo, (int, float)) or not isinstance(hi, (int, float)):
        return None
    if abs(lo - hi) < 1e-3:
        return fmt_si(lo, "V")
    return f"{fmt_si(lo, 'V')} to {fmt_si(hi, 'V')}"


def _fixed_at(row: dict, volts: float) -> bool:
    lo, hi = row.get("output_voltage_min"), row.get("output_voltage_max")
    return (isinstance(lo, (int, float)) and isinstance(hi, (int, float))
            and abs(lo - volts) <= 1e-3 and abs(hi - volts) <= 1e-3)


def _package(*choices: str) -> Filter:
    return Filter("package", "Package", "choice", "package", choices=choices)


_BASIC = Filter("basic", "Basic parts only", "bool", "is_basic")
_PASSIVE = ("0201", "0402", "0603", "0805", "1206")
_V = _si("V")
_A = _si("A")

CATEGORIES: dict[str, Category] = {c.slug: c for c in (
    Category(
        "resistors", "Resistors",
        (_package(*_PASSIVE),
         Filter("resistance", "Resistance", "number", "resistance",
                unit="ohm", example="10k"),
         _BASIC),
        (Column("Resistance", _field("resistance", lambda v: fmt_ohms(float(v)))),
         Column("Tolerance", _field("tolerance_fraction", _percent)),
         Column("Power", _field("power_watts", _milliwatts)))),
    Category(
        "capacitors", "Capacitors",
        (_package(*_PASSIVE),
         Filter("capacitance", "Capacitance", "number", "capacitance",
                unit="F", example="100n"),
         _BASIC),
        (Column("Capacitance", _field("capacitance_farads",
                                      lambda v: fmt_farads(float(v)))),
         Column("Voltage", _field("voltage_rating", _V)),
         Column("Tolerance", _field("tolerance_fraction", _percent)),
         Column("Dielectric", _field("temperature_coefficient", _text)))),
    Category(
        "leds", "LEDs",
        (_package("0402", "0603", "0805", "1206"),
         Filter("color", "Color", "choice", "color",
                choices=("red", "green", "blue", "white", "yellow",
                         "orange", "emerald"))),
        (Column("Color", _field("color", _text)),
         Column("Forward voltage", _field("forward_voltage", _V)),
         Column("Forward current", _field("forward_current", _A))),
        note="Many LEDs carry no color in the source data, so a color filter"
             " leaves those out."),
    Category(
        "diodes", "Diodes",
        (_package("SOD-123", "SOD-123FL", "SOD-323", "SOD-523", "SOT-23",
                  "SMA(DO-214AC)", "SMB(DO-214AA)"),),
        (Column("Forward voltage", _field("forward_voltage", _V)),
         Column("Reverse voltage", _field("reverse_voltage", _V)),
         Column("Forward current", _field("forward_current", _A))),
        note="The source data does not type diodes, so filter by package and"
             " check the specs."),
    Category(
        "mosfets", "MOSFETs",
        (_package("SOT-23", "SOT-323", "SOT-363", "SOP-8", "TO-252",
                  "TO-220AB"),
         Filter("min_vds", "Min Vds", "number", "drain_source_voltage_min",
                unit="V", example="30"),
         Filter("min_id", "Min Id", "number", "continuous_drain_current_min",
                unit="A", example="2")),
        # Gate threshold is deliberately absent: upstream reports 400 for a
        # 30V part, so it is wrong in a way no formatting can fix.
        (Column("Vds", _field("drain_source_voltage", _V)),
         Column("Id", _field("continuous_drain_current", _A)))),
    Category(
        "ldos", "LDOs",
        (_package("SOT-23", "SOT-23-5", "SOT-223", "SOT-89",
                  "WSON-6-EP(2x2)"),
         Filter("output_voltage", "Output voltage", "number",
                "output_voltage", unit="V", example="3.3", refine=_fixed_at)),
        (Column("Output voltage", _ldo_output),
         Column("Max current", _field("output_current_max", _A)),
         Column("Dropout", _field("dropout_voltage", _V))),
        note="Only fixed-output parts at exactly this voltage are shown."),
)}


def catalog() -> CategoriesResponse:
    return CategoriesResponse(categories=[
        CategorySpec(slug=c.slug, label=c.label, note=c.note, filters=[
            FilterSpec(name=f.name, label=f.label, kind=f.kind, unit=f.unit,
                       choices=list(f.choices) or None, example=f.example)
            for f in c.filters])
        for c in CATEGORIES.values()])


def _short(value: str) -> str:
    return value.strip()[:40]


def _plain(n: float) -> str:
    return str(int(n)) if n.is_integer() else repr(n)


def build_query(cat: Category, params: list[tuple[str, str]]
                ) -> tuple[dict[str, str], list[tuple[Filter, float]]]:
    by_name = {f.name: f for f in cat.filters}
    seen: set[str] = set()
    upstream: dict[str, str] = {}
    refines: list[tuple[Filter, float]] = []
    for name, raw in params:
        f = by_name.get(name)
        if f is None:
            raise BadFilter(f"{cat.label} cannot be filtered by '{_short(name)}'.")
        if name in seen:
            raise BadFilter(f"'{f.name}' was given more than once.")
        seen.add(name)
        value = raw.strip()
        if not value:
            continue
        if f.kind == "choice":
            match = next((c for c in f.choices if c.lower() == value.lower()), None)
            if match is None:
                raise BadFilter(f"'{_short(value)}' is not a {f.label.lower()}"
                                f" we list for {cat.label}.")
            upstream[f.upstream] = match
        elif f.kind == "bool":
            if value.lower() == "false":
                continue
            if value.lower() != "true":
                raise BadFilter(f"'{f.label}' takes true or false.")
            upstream[f.upstream] = "true"
        else:
            try:
                number = parse_si(value, f.unit)
            except ValueError as exc:
                raise BadFilter(str(exc)) from exc
            upstream[f.upstream] = _plain(number)
            if f.refine is not None:
                refines.append((f, number))
    return upstream, refines


def map_row(cat: Category, raw: dict) -> dict | None:
    """Built field by field. Nothing is copied across wholesale, so price1,
    and any field upstream adds later, cannot reach a response."""
    mpn = str(raw.get("mfr") or "").strip()
    key = normalize_exact(mpn)
    code = raw.get("lcsc")
    if not key or code is None:
        return None
    return {"mpn": mpn, "mpn_key": key, "lcsc": f"C{code}",
            "package": str(raw.get("package") or ""),
            # null is upstream having no count, which is not a count of zero.
            "stock": None if raw.get("stock") is None else int(raw["stock"]),
            "specs": [[c.label, c.read(raw)] for c in cat.columns]}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BrowseService:
    def __init__(self, adapter, store=None, ttl_secs: int = 0,
                 now: Callable[[], datetime] = _utc_now):
        self._adapter = adapter
        self._store = store
        self._ttl = ttl_secs
        self._now = now

    async def browse(self, slug: str, params: list[tuple[str, str]]
                     ) -> BrowseResponse:
        cat = CATEGORIES.get(slug)
        if cat is None:
            raise UnknownCategory(slug)
        upstream, refines = build_query(cat, params)
        # Every refine value is also an upstream param, so the key fixes the
        # whole answer and the finished rows are what gets cached.
        key = f"browse|{slug}|{urlencode(sorted(upstream.items()))}"
        if self._store is not None:
            hit = await self._store.get_parametric(key)
            if hit is not None and \
                    (self._now() - hit[1]).total_seconds() < self._ttl:
                return _response(slug, hit[0][0], hit[1])
        raw = await self._adapter.list_category(
            cat.path, cat.slug, {**upstream, "limit": UPSTREAM_CAP})
        as_of = self._now()
        kept = [r for r in raw if all(f.refine(r, v) for f, v in refines)]
        rows = [m for m in (map_row(cat, r) for r in kept) if m is not None]
        # One-element list because put_parametric stores a list of dicts and
        # capped has to survive the cache along with the rows.
        answer = {"capped": len(raw) >= UPSTREAM_CAP, "results": rows}
        if self._store is not None:
            await self._store.put_parametric(key, [answer], as_of)
        return _response(slug, answer, as_of)


def _response(slug: str, answer: dict, as_of: datetime) -> BrowseResponse:
    rows = [BrowseRow(**r) for r in answer["results"]]
    return BrowseResponse(category=slug, results=rows, count=len(rows),
                          capped=answer["capped"], as_of=as_of)
