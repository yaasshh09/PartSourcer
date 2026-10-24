"""The CLI prices a BOM on the same rules as the site's BOM check.

Run with: python -m pytest cli -q
"""

import json

import partsourcer as ps


def offer(**over):
    o = {"distributor": "lcsc", "sku": "C1", "match_tier": "exact", "currency": "USD",
         "stock": 5000, "in_stock": True, "price_usd": 0.01, "price_breaks": None,
         "as_of": "2026-10-24T01:00:00+00:00"}
    o.update(over)
    return o


def part(key, *offers):
    return {"part": {"mpn_key": key, "mpn": key, "offers": list(offers)}}


def test_reads_a_kicad_export_by_its_headers():
    text = 'Reference,Value,Footprint,Qty,MPN\n"R1,R2",10k,0402,2,0402WGF1002TCE\nC1,100n,0402,1,CL05B104KO5NNNC\n'
    assert ps.parse_bom(text) == [{"mpn": "0402WGF1002TCE", "qty": 2},
                                  {"mpn": "CL05B104KO5NNNC", "qty": 1}]


def test_counts_designators_when_there_is_no_quantity_column():
    text = 'Designator,Comment,LCSC Part #\n"R1,R2,R3",10k,C25744\n'
    assert ps.parse_bom(text) == [{"mpn": "C25744", "qty": 3}]


def test_a_plain_list_in_either_order_and_repeats_add_up():
    assert ps.parse_bom("NE555P 4\n2 ne555p\n# note\nLM358\n") == [
        {"mpn": "NE555P", "qty": 6}, {"mpn": "LM358", "qty": 1}]


def test_a_header_without_a_part_number_column_is_refused():
    try:
        ps.parse_bom("Value,Qty\n10k,2\n")
    except ps.CheckFailed as e:
        assert "part number" in str(e)
    else:
        raise AssertionError("expected CheckFailed")


def test_price_breaks_below_the_first_step_buy_the_minimum():
    o = offer(distributor="mouser", price_breaks=[{"qty": 10, "price_usd": 0.1}, {"qty": 100, "price_usd": 0.05}])
    assert ps.price_at(o, 3) == (0.1, 10, 1.0, "minimum order 10")
    assert ps.price_at(o, 150)[2] == 7.5
    assert ps.price_at(offer(price_usd=None), 5) is None


def test_cheapest_offer_that_fills_the_order_wins():
    p = part("X", offer(price_usd=0.02), offer(distributor="mouser", sku="M", price_usd=0.01, stock=5))
    r = ps.check_line(p["part"], 10)
    assert (r["state"], r["distributor"], r["total"]) == ("ok", "lcsc", 0.2)


def test_short_unpriced_and_packaging_variants():
    assert ps.check_line(part("X", offer(stock=3))["part"], 10) == {"state": "short", "best_stock": 3}
    assert ps.check_line(part("X", offer(price_usd=None))["part"], 1) == {"state": "unpriced"}
    assert ps.check_line(part("X", offer(match_tier="packaging"))["part"], 1) == {"state": "unpriced"}


def test_check_multiplies_boards_and_reports_missing_and_errors():
    def fetch(path):
        if path == "/part/A":
            return part("A", offer())
        if path == "/part/B":
            return None
        raise ps.CheckFailed("Upstream timed out")
    rows = ps.check([{"mpn": "A", "qty": 2}, {"mpn": "B", "qty": 1}, {"mpn": "C", "qty": 1}],
                    boards=5, fetch=fetch)
    assert [(r["mpn"], r["qty"], r["state"]) for r in rows] == [
        ("A", 10, "ok"), ("B", 5, "missing"), ("C", 5, "error")]
    assert rows[2]["detail"] == "Upstream timed out"
    text = ps.render(rows)
    assert "Total for the lines that can be bought: $0.1000" in text
    assert "2 of 3 lines cannot be bought" in text


def test_swaps_ride_along_when_asked():
    def fetch(path):
        if path.startswith("/part/"):
            return part("R1", offer())
        return {"equivalent": {"mpn": "R2", "lcsc": "C2", "percent_cheaper": 40, "match_reason": "same 10k 0402"}}
    rows = ps.check([{"mpn": "R1", "qty": 1}], swaps=True, fetch=fetch)
    assert rows[0]["swap"] == {"mpn": "R2", "lcsc": "C2", "percent_cheaper": 40, "reason": "same 10k 0402"}
    assert "cheaper drop-in R2 (C2), 40% cheaper" in ps.render(rows)


def test_exit_codes(tmp_path, monkeypatch, capsys):
    bom = tmp_path / "bom.csv"
    bom.write_text("A 1\n", encoding="utf-8")
    monkeypatch.setattr(ps, "check", lambda lines, boards=1, swaps=False: [
        {"mpn": "A", "qty": 1, **ps.check_line(part("A", offer())["part"], 1)}])
    assert ps.main(["check", str(bom), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["lines"][0]["state"] == "ok"
    monkeypatch.setattr(ps, "check", lambda lines, boards=1, swaps=False: [{"mpn": "A", "qty": 1, "state": "missing"}])
    assert ps.main(["check", str(bom)]) == 1
    assert ps.main(["check", str(tmp_path / "nope.csv")]) == 2
