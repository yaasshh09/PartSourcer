"""Browse by category: what goes upstream, what comes back, what is cached."""

from datetime import datetime, timedelta, timezone

import httpx
import pytest

from cache.store import SqliteCacheStore
from services.adapters.base import UpstreamError
from services.adapters.lcsc import LcscAdapter
from services.browse import (CATEGORIES, BadFilter, BrowseService,
                             UnknownCategory, catalog)

pytestmark = pytest.mark.anyio

RES = {"lcsc": 25804, "mfr": "0603WAF1002T5E", "package": "0603",
       "stock": 37165617, "price1": 0.000842857, "in_stock": True,
       "resistance": 10000, "tolerance_fraction": 0.01, "power_watts": 100,
       "is_basic": True}


def ldo(lcsc, lo, hi):
    return {"lcsc": lcsc, "mfr": f"LDO{lcsc}", "package": "SOT-23-5",
            "stock": 1000, "price1": 0.1, "output_voltage_min": lo,
            "output_voltage_max": hi, "output_current_max": 0.3,
            "dropout_voltage": 0.2}


class Upstream:
    def __init__(self, rows, status=200):
        self.rows, self.status, self.calls = rows, status, []

    def __call__(self, request):
        self.calls.append(request)
        if self.status != 200:
            return httpx.Response(self.status, json={})
        envelope = request.url.path.split("/")[1]
        return httpx.Response(200, json={envelope: self.rows})

    @property
    def sent(self):
        return dict(self.calls[-1].url.params)


class Clock:
    def __init__(self):
        self.t = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.t


def make(upstream, store=None, ttl=3600, clock=None):
    client = httpx.AsyncClient(transport=httpx.MockTransport(upstream),
                               base_url="https://jlcsearch.test")
    return BrowseService(LcscAdapter(client), store=store, ttl_secs=ttl,
                         now=clock or Clock())


@pytest.fixture
def store(tmp_path):
    s = SqliteCacheStore(str(tmp_path / "c.db"))
    s.open()
    yield s
    s.close()


# --- what goes upstream -----------------------------------------------------

async def test_resistance_goes_upstream_in_plain_ohms():
    up = Upstream([RES])
    await make(up).browse("resistors", [("package", "0603"), ("resistance", "10k")])
    assert up.calls[0].url.path == "/resistors/list.json"
    assert up.sent == {"package": "0603", "resistance": "10000", "limit": "100"}


async def test_4k7_is_4700_not_text():
    up = Upstream([RES])
    await make(up).browse("resistors", [("resistance", "4k7")])
    assert up.sent["resistance"] == "4700"


async def test_zero_ohm_is_a_real_value():
    up = Upstream([RES])
    await make(up).browse("resistors", [("resistance", "0")])
    assert up.sent["resistance"] == "0"


async def test_capacitance_goes_upstream_in_farads():
    up = Upstream([])
    await make(up).browse("capacitors", [("capacitance", "100nF")])
    assert up.sent["capacitance"] == "1e-07"


async def test_led_color_is_sent_lowercase():
    up = Upstream([])
    await make(up).browse("leds", [("color", "RED")])
    assert up.sent["color"] == "red"


async def test_package_matches_loosely_but_goes_up_exact():
    up = Upstream([])
    await make(up).browse("mosfets", [("package", "sot-23")])
    assert up.sent["package"] == "SOT-23"


async def test_basic_true_is_sent_and_false_is_dropped():
    up = Upstream([])
    svc = make(up)
    await svc.browse("resistors", [("basic", "true")])
    assert up.sent["is_basic"] == "true"
    await svc.browse("resistors", [("basic", "false")])
    assert "is_basic" not in up.sent


async def test_mosfet_minimums_use_upstream_names():
    up = Upstream([])
    await make(up).browse("mosfets", [("min_vds", "30"), ("min_id", "500m")])
    assert up.sent["drain_source_voltage_min"] == "30"
    assert up.sent["continuous_drain_current_min"] == "0.5"


async def test_empty_values_are_ignored():
    up = Upstream([])
    await make(up).browse("resistors", [("package", ""), ("resistance", "  ")])
    assert up.sent == {"limit": "100"}


# --- what is refused ----------------------------------------------------------

async def test_unknown_category():
    with pytest.raises(UnknownCategory):
        await make(Upstream([])).browse("rockets", [])


@pytest.mark.parametrize("params,needle", [
    ([("colour", "red")], "colour"),
    ([("package", "0603"), ("package", "0805")], "more than once"),
    ([("package", "0604")], "0604"),
    ([("resistance", "10V")], "10k"),
    ([("basic", "maybe")], "true or false"),
])
async def test_bad_filters_say_why(params, needle):
    up = Upstream([])
    with pytest.raises(BadFilter) as exc:
        await make(up).browse("resistors", params)
    assert needle in str(exc.value)
    assert up.calls == []


async def test_a_huge_value_gets_a_short_message():
    with pytest.raises(BadFilter) as exc:
        await make(Upstream([])).browse("resistors", [("package", "x" * 5000)])
    assert len(str(exc.value)) < 200


# --- what comes back ------------------------------------------------------------

async def test_a_row_maps_to_specs_and_stock():
    out = await make(Upstream([RES])).browse("resistors", [])
    row = out.results[0]
    assert (row.mpn, row.mpn_key, row.lcsc, row.package, row.stock) == \
        ("0603WAF1002T5E", "0603WAF1002T5E", "C25804", "0603", 37165617)
    assert row.specs == [("Resistance", "10 kOhm"), ("Tolerance", "±1%"),
                         ("Power", "100 mW")]


async def test_no_price_reaches_the_response():
    out = await make(Upstream([RES])).browse("resistors", [])
    body = out.model_dump_json()
    assert "price" not in body
    assert "0.000842857" not in body


async def test_missing_and_unreadable_specs_are_null():
    rows = [{**RES, "tolerance_fraction": None, "resistance": "junk"}]
    out = await make(Upstream(rows)).browse("resistors", [])
    specs = dict(out.results[0].specs)
    assert specs["Tolerance"] is None and specs["Resistance"] is None


async def test_rows_without_an_mpn_are_dropped():
    out = await make(Upstream([{**RES, "mfr": "  "}, RES])).browse("resistors", [])
    assert out.count == 1


async def test_mosfet_gate_threshold_is_never_shown():
    row = {"lcsc": 1, "mfr": "AO3401A", "package": "SOT-23", "stock": 5,
           "drain_source_voltage": 30, "continuous_drain_current": 4.2,
           "gate_threshold_voltage": 400}
    out = await make(Upstream([row])).browse("mosfets", [])
    assert out.results[0].specs == [("Vds", "30 V"), ("Id", "4.2 A")]
    assert "400" not in out.model_dump_json()


async def test_ldo_voltage_keeps_only_exact_fixed_parts():
    rows = [ldo(1, 3.3, 3.3), ldo(2, 1.8, 1.8), ldo(3, 1.2, 5.5)]
    up = Upstream(rows)
    out = await make(up).browse("ldos", [("output_voltage", "3.3")])
    assert up.sent["output_voltage"] == "3.3"
    assert [r.lcsc for r in out.results] == ["C1"]
    assert dict(out.results[0].specs)["Output voltage"] == "3.3 V"


async def test_capped_is_measured_before_refining():
    rows = [ldo(1, 3.3, 3.3)] + [ldo(i, 1.8, 1.8) for i in range(2, 101)]
    out = await make(Upstream(rows)).browse("ldos", [("output_voltage", "3.3")])
    assert out.count == 1 and out.capped is True


async def test_a_short_list_is_not_capped():
    out = await make(Upstream([RES])).browse("resistors", [])
    assert out.capped is False


async def test_adjustable_ldo_shows_its_range():
    out = await make(Upstream([ldo(3, 1.2, 5.5)])).browse("ldos", [])
    assert dict(out.results[0].specs)["Output voltage"] == "1.2 V to 5.5 V"


# --- cache ------------------------------------------------------------------------

async def test_a_fresh_cache_row_skips_upstream_and_keeps_capped(store):
    up = Upstream([RES] * 100)
    svc = make(up, store=store)
    first = await svc.browse("resistors", [("package", "0603")])
    second = await svc.browse("resistors", [("package", "0603")])
    assert len(up.calls) == 1
    assert second.capped is True and second.count == first.count
    assert second.as_of == first.as_of


async def test_an_expired_row_is_refetched(store):
    clock = Clock()
    up = Upstream([RES])
    svc = make(up, store=store, clock=clock)
    await svc.browse("resistors", [])
    clock.t += timedelta(hours=2)
    await svc.browse("resistors", [])
    assert len(up.calls) == 2


async def test_upstream_down_on_a_stale_row_is_an_error_not_old_data(store):
    clock = Clock()
    up = Upstream([RES])
    svc = make(up, store=store, clock=clock)
    await svc.browse("resistors", [])
    clock.t += timedelta(hours=2)
    up.status = 500
    with pytest.raises(UpstreamError):
        await svc.browse("resistors", [])


# --- the schema ---------------------------------------------------------------------

def test_catalog_lists_the_six_categories_in_order():
    slugs = [c.slug for c in catalog().categories]
    assert slugs == ["resistors", "capacitors", "leds", "diodes", "mosfets", "ldos"]
    assert list(CATEGORIES) == slugs


def test_number_filters_carry_an_example_for_the_placeholder():
    res = next(c for c in catalog().categories if c.slug == "resistors")
    resistance = next(f for f in res.filters if f.name == "resistance")
    assert resistance.kind == "number" and resistance.example == "10k"


def test_map_row_copies_only_what_it_names():
    """The response model would drop a price anyway; this pins the row
    itself, because that row is also what the cache stores."""
    from services.browse import map_row
    row = map_row(CATEGORIES["resistors"], RES)
    assert set(row) == {"mpn", "mpn_key", "lcsc", "package", "stock", "specs"}


def test_a_stock_upstream_did_not_publish_stays_null():
    # Upstream sends null where it has no count and 0 where it has none.
    # On 2026-10-27 C25804, usually millions in stock, came back null.
    from models.browse import BrowseRow
    from services.browse import map_row
    unknown = map_row(CATEGORIES["resistors"], dict(RES, stock=None))
    assert unknown["stock"] is None
    assert BrowseRow(**unknown).stock is None
    assert map_row(CATEGORIES["resistors"], dict(RES, stock=0))["stock"] == 0
