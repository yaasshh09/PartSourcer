import { headlineOffer } from './offers.js'

export const MAX_WATCH = 50
const STORAGE_KEY = 'ps-watch'

/**
 * What a part looked like when it was watched. The distributor and SKU are
 * kept so a later read is compared with that same listing: the headline can
 * move to another distributor, and two distributors' prices are not a change.
 */
export function snapshot(part, added = new Date().toISOString()) {
  const h = headlineOffer(part)
  return {
    k: part.mpn_key, mpn: part.mpn,
    distributor: h ? h.distributor : null, sku: h ? h.sku : null,
    price_usd: h ? h.price_usd : null, stock: h ? h.stock : null,
    as_of: (h && h.as_of) || part.as_of || null, added,
  }
}

function clean(list) {
  return (Array.isArray(list) ? list : [])
    .filter((e) => e && typeof e.k === 'string' && e.k && e.k.length <= 200)
    .slice(0, MAX_WATCH)
}

// Blocked or hand-edited storage starts an empty list instead of an error.
export function loadWatch() {
  try {
    return clean(JSON.parse(window.localStorage.getItem(STORAGE_KEY) || '[]'))
  } catch {
    return []
  }
}

export function saveWatch(list) {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(list))
  } catch {
    // Convenience only.
  }
}

/** Newest first; a second press removes it; the oldest drops off past the cap. */
export function toggleWatch(list, part) {
  if (list.some((e) => e.k === part.mpn_key)) return list.filter((e) => e.k !== part.mpn_key)
  return [snapshot(part), ...list].slice(0, MAX_WATCH)
}

/** The same listing now, and how far its price and stock moved. */
export function sinceAdded(entry, part) {
  const offer = entry.distributor
    ? ((part && part.offers) || []).find((o) => o.distributor === entry.distributor && o.sku === entry.sku) || null
    : null
  if (!offer) return { offer: null, priceDelta: null, stockDelta: null }
  return {
    offer,
    priceDelta: offer.price_usd != null && entry.price_usd != null ? offer.price_usd - entry.price_usd : null,
    stockDelta: offer.stock != null && entry.stock != null ? offer.stock - entry.stock : null,
  }
}
