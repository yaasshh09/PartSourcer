from datetime import datetime, timezone

from models.offer import DistributorStatus, Offer
from services.cheapest import compute_cheapest

T = datetime(2026, 8, 8, 9, 14, tzinfo=timezone.utc)


def offer(distributor, price, tier="exact", in_stock=True, currency="USD"):
    return Offer(distributor=distributor, sku=f"{distributor}-1",
                 mpn_as_listed="X", match_tier=tier, match_note=None,
                 stock=100 if in_stock else 0, in_stock=in_stock,
                 price_usd=price, price_breaks=None, currency=currency,
                 product_url=None, as_of=T)


def ok(*names):
    return [DistributorStatus(distributor=n, state="ok", detail=None, as_of=T)
            for n in names]


def all_three(ok_names):
    states = []
    for n in ("lcsc", "mouser", "digikey"):
        states.append(DistributorStatus(
            distributor=n, state="ok" if n in ok_names else "unavailable",
            detail=None, as_of=T if n in ok_names else None))
    return states


def test_picks_the_lowest_exact_in_stock_usd_offer():
    c, reason = compute_cheapest(
        [offer("lcsc", 1.82), offer("mouser", 2.94), offer("digikey", 1.10)],
        all_three(["lcsc", "mouser", "digikey"]))
    assert reason is None
    assert (c.distributor, c.price_usd, c.compared_sources, c.of_sources) == (
        "digikey", 1.10, 3, 3)


def test_packaging_tier_never_wins_the_headline():
    c, reason = compute_cheapest(
        [offer("lcsc", 1.82), offer("mouser", 0.99, tier="packaging")],
        all_three(["lcsc", "mouser"]))
    assert c.distributor == "lcsc" and c.price_usd == 1.82
    assert reason is None


def test_out_of_stock_is_excluded():
    c, _ = compute_cheapest(
        [offer("lcsc", 1.82), offer("mouser", 0.50, in_stock=False)],
        all_three(["lcsc", "mouser"]))
    assert c.distributor == "lcsc"


def test_non_usd_is_excluded():
    c, _ = compute_cheapest(
        [offer("lcsc", 1.82), offer("mouser", 0.50, currency="EUR")],
        all_three(["lcsc", "mouser"]))
    assert c.distributor == "lcsc"


def test_single_source_gives_no_claim_and_a_reason():
    c, reason = compute_cheapest([offer("lcsc", 1.82)], all_three(["lcsc"]))
    assert c is None
    assert reason == "compared 1 of 3 sources, need at least 2 to name a cheapest"


def test_zero_sources_gives_no_claim():
    c, reason = compute_cheapest([], all_three([]))
    assert c is None
    assert "0 of 3" in reason


def test_quorum_met_but_nothing_eligible():
    c, reason = compute_cheapest(
        [offer("lcsc", 1.82, in_stock=False), offer("mouser", 2.0, in_stock=False)],
        all_three(["lcsc", "mouser"]))
    assert c is None
    assert reason == "no in-stock USD offer for the exact part"


def test_ties_prefer_earlier_distributor_precedence():
    c, _ = compute_cheapest(
        [offer("mouser", 1.00), offer("lcsc", 1.00)],
        all_three(["lcsc", "mouser"]))
    assert c.distributor == "lcsc"
