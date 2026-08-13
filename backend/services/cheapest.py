"""The cheapest claim, and the rules that stop it lying.

Three gates, all load-bearing:
  1. Quorum. Fewer than two answering sources means no claim at all.
  2. Tier. Only exact-MPN offers compete. A packaging variant is a
     different physical product and is surfaced separately.
  3. Comparability. In stock and priced in USD, because we do no FX.
"""

from models.offer import Cheapest, DistributorStatus, Offer

DISTRIBUTOR_PRECEDENCE = ("lcsc", "mouser", "digikey")
MIN_SOURCES_FOR_CLAIM = 2


def compute_cheapest(
    offers: list[Offer],
    sources: list[DistributorStatus],
) -> tuple[Cheapest | None, str | None]:
    """Return (claim, None) or (None, human-readable reason)."""
    # A disabled distributor has no credentials, so it was never contacted.
    # Counting it would describe a source that was asked and failed, and in
    # the deploy where only LCSC is configured that reads as two dead
    # distributors rather than two we never set up.
    contacted = [s for s in sources if s.state != "disabled"]
    answered = sum(1 for s in contacted if s.state == "ok")
    asked = len(contacted)

    if answered < MIN_SOURCES_FOR_CLAIM:
        return None, (f"compared {answered} of {asked} sources, "
                      f"need at least {MIN_SOURCES_FOR_CLAIM} to name a cheapest")

    eligible = [o for o in offers
                if o.match_tier == "exact" and o.in_stock and o.currency == "USD"]
    if not eligible:
        return None, "no in-stock USD offer for the exact part"

    best = min(eligible, key=lambda o: (
        o.price_usd, DISTRIBUTOR_PRECEDENCE.index(o.distributor)))
    return Cheapest(distributor=best.distributor, sku=best.sku,
                    price_usd=best.price_usd, compared_sources=answered,
                    of_sources=asked), None
