/**
 * Pure reading rules for the v2 multi-distributor shape.
 *
 * Every surface that shows a price goes through headlineOffer, so search
 * results and the detail header can never disagree about what a part costs.
 * No React and no fetch in here, so these rules are cheap to test exhaustively.
 */

export const DISTRIBUTOR_LABEL = {
  lcsc: 'LCSC', mouser: 'Mouser', digikey: 'DigiKey',
}

export const SOURCE_STATE_COPY = {
  timeout: 'timed out',
  unavailable: 'unavailable',
  quota_exhausted: 'daily quota used up',
}

// Matches backend/services/cheapest.py, so a tie breaks the same way here.
const PRECEDENCE = ['lcsc', 'mouser', 'digikey']

function precedence(distributor) {
  const i = PRECEDENCE.indexOf(distributor)
  return i === -1 ? PRECEDENCE.length : i
}

// A distributor that published no price sends null. Subtracting it reads as
// zero, which would sort an unpriced offer ahead of every real one and make
// it the headline. It sorts last instead.
function sortablePrice(offer) {
  return offer.price_usd == null ? Number.POSITIVE_INFINITY : offer.price_usd
}

function byStockThenPrice(a, b) {
  if (a.in_stock !== b.in_stock) return a.in_stock ? -1 : 1
  const pa = sortablePrice(a)
  const pb = sortablePrice(b)
  if (pa !== pb) return pa - pb
  return precedence(a.distributor) - precedence(b.distributor)
}

/**
 * The one offer a surface shows as "the price" for this part.
 *
 * The backend's cheapest claim already passed the quorum, tier and
 * comparability gates, so when it names one that is the answer. It is null
 * whenever fewer than two sources answered, which is the normal state of a
 * single-source deploy, so the fallback below is the production path: prefer
 * a real in-stock exact-match offer, and only then take whatever is left.
 * Skipping straight to "cheapest overall" would let an out-of-stock listing
 * become the headline price on a part that has an in-stock one.
 */
export function headlineOffer(part) {
  const offers = (part && part.offers) || []
  if (!offers.length) return null

  const claim = part.cheapest
  if (claim) {
    const named = offers.find(
      (o) => o.distributor === claim.distributor && o.sku === claim.sku)
    if (named) return named
  }

  const comparable = offers.filter(
    (o) => o.match_tier === 'exact' && o.in_stock && o.currency === 'USD')
  if (comparable.length) return comparable.sort(byStockThenPrice)[0]

  return offers.slice().sort(byStockThenPrice)[0]
}

/**
 * The sources worth warning the user about.
 *
 * "disabled" means no credentials were configured, so the distributor was
 * never contacted. Reporting it would describe a failure that did not happen,
 * and on a deploy that never had those keys it would pin a permanent warning
 * to every page.
 */
export function degradedSources(sources) {
  return (sources || []).filter((s) => s.state !== 'ok' && s.state !== 'disabled')
}

/**
 * Exact matches and packaging variants, kept apart.
 *
 * A packaging-tier offer is a different physical product (tape and reel
 * versus tube). Merged into one price-sorted list, a cheaper reel would
 * silently undercut the tube the user actually searched for.
 */
export function groupOffersByTier(offers) {
  const all = offers || []
  return {
    exact: all.filter((o) => o.match_tier === 'exact').sort(byStockThenPrice),
    packaging: all.filter((o) => o.match_tier === 'packaging').sort(byStockThenPrice),
  }
}

/** The exact-tier LCSC listing, which is the only one that carries an LCSC code. */
export function lcscOffer(part) {
  const offers = (part && part.offers) || []
  return offers.find(
    (o) => o.distributor === 'lcsc' && o.match_tier === 'exact') || null
}

/**
 * The oldest as_of across a result set. A fast distributor must never make
 * the page look fresher than its stalest record, which is the same rule
 * Part.as_of applies across offers.
 */
export function oldestAsOf(parts) {
  const stamps = (parts || []).map((p) => p && p.as_of).filter(Boolean)
  if (!stamps.length) return null
  return stamps.reduce((a, b) => (new Date(a) <= new Date(b) ? a : b))
}
