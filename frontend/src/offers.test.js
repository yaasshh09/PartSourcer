import { describe, test, expect } from 'vitest'
import {
  headlineOffer, degradedSources, groupOffersByTier, lcscOffer, oldestAsOf,
  DISTRIBUTOR_LABEL, SOURCE_STATE_COPY,
} from './offers.js'

function offer(over = {}) {
  return {
    distributor: 'lcsc', sku: 'C25531', mpn_as_listed: 'NE555P',
    match_tier: 'exact', match_note: null, stock: 100, in_stock: true,
    price_usd: 1, price_breaks: null, currency: 'USD', product_url: null,
    as_of: '2026-08-15T00:00:00Z', is_basic: null, is_preferred: null,
    ...over,
  }
}

describe('headlineOffer', () => {
  test('returns null when the part has no offers', () => {
    expect(headlineOffer({ offers: [], cheapest: null })).toBeNull()
  })

  test('returns the offer the backend named as cheapest', () => {
    const cheap = offer({ distributor: 'mouser', sku: 'M-1', price_usd: 0.5 })
    const part = {
      offers: [offer(), cheap],
      cheapest: { distributor: 'mouser', sku: 'M-1', price_usd: 0.5, compared_sources: 2, of_sources: 2 },
    }
    expect(headlineOffer(part)).toBe(cheap)
  })

  test('matches the claim on distributor AND sku, not price alone', () => {
    const wanted = offer({ distributor: 'digikey', sku: 'D-9', price_usd: 2 })
    const part = {
      offers: [offer({ price_usd: 2 }), wanted],
      cheapest: { distributor: 'digikey', sku: 'D-9', price_usd: 2, compared_sources: 2, of_sources: 2 },
    }
    expect(headlineOffer(part)).toBe(wanted)
  })

  test('with no claim, prefers an in-stock exact USD offer over a cheaper out-of-stock one', () => {
    const inStock = offer({ sku: 'IN', price_usd: 5, in_stock: true })
    const cheaperDead = offer({ sku: 'DEAD', price_usd: 1, in_stock: false, stock: 0 })
    expect(headlineOffer({ offers: [cheaperDead, inStock], cheapest: null })).toBe(inStock)
  })

  test('with no claim, picks the cheapest among in-stock exact USD offers', () => {
    const a = offer({ sku: 'A', price_usd: 3 })
    const b = offer({ sku: 'B', price_usd: 2 })
    expect(headlineOffer({ offers: [a, b], cheapest: null })).toBe(b)
  })

  test('ignores packaging-tier and non-USD offers in the preferred pass', () => {
    const reel = offer({ sku: 'REEL', price_usd: 0.1, match_tier: 'packaging', match_note: 'tape and reel (T&R)' })
    const eur = offer({ sku: 'EUR', price_usd: 0.2, currency: 'EUR' })
    const plain = offer({ sku: 'PLAIN', price_usd: 1 })
    expect(headlineOffer({ offers: [reel, eur, plain], cheapest: null })).toBe(plain)
  })

  test('falls back to the cheapest offer overall when nothing is in stock', () => {
    const a = offer({ sku: 'A', price_usd: 3, in_stock: false, stock: 0 })
    const b = offer({ sku: 'B', price_usd: 2, in_stock: false, stock: 0 })
    expect(headlineOffer({ offers: [a, b], cheapest: null })).toBe(b)
  })

  test('falls back when the named claim is not present in the offer list', () => {
    const only = offer({ sku: 'ONLY', price_usd: 4 })
    const part = {
      offers: [only],
      cheapest: { distributor: 'mouser', sku: 'GONE', price_usd: 1, compared_sources: 2, of_sources: 2 },
    }
    expect(headlineOffer(part)).toBe(only)
  })
})

describe('degradedSources', () => {
  test('returns an empty array when every source answered', () => {
    const sources = [
      { distributor: 'lcsc', state: 'ok', detail: null, as_of: null },
      { distributor: 'mouser', state: 'ok', detail: null, as_of: null },
    ]
    expect(degradedSources(sources)).toEqual([])
  })

  test('excludes disabled sources, which were never contacted', () => {
    const sources = [
      { distributor: 'lcsc', state: 'ok', detail: null, as_of: null },
      { distributor: 'mouser', state: 'disabled', detail: 'no api key', as_of: null },
      { distributor: 'digikey', state: 'disabled', detail: 'no api key', as_of: null },
    ]
    expect(degradedSources(sources)).toEqual([])
  })

  test('returns the sources that were asked and failed', () => {
    const sources = [
      { distributor: 'lcsc', state: 'ok', detail: null, as_of: null },
      { distributor: 'mouser', state: 'timeout', detail: 'read timeout', as_of: null },
      { distributor: 'digikey', state: 'quota_exhausted', detail: null, as_of: null },
    ]
    expect(degradedSources(sources).map((s) => s.distributor)).toEqual(['mouser', 'digikey'])
  })

  test('tolerates a missing sources array', () => {
    expect(degradedSources(undefined)).toEqual([])
  })
})

describe('groupOffersByTier', () => {
  test('splits exact from packaging', () => {
    const e = offer({ sku: 'E' })
    const p = offer({ sku: 'P', match_tier: 'packaging', match_note: 'tape and reel (T&R)' })
    const out = groupOffersByTier([p, e])
    expect(out.exact.map((o) => o.sku)).toEqual(['E'])
    expect(out.packaging.map((o) => o.sku)).toEqual(['P'])
  })

  test('sorts in-stock first, then by price, then by distributor precedence', () => {
    const dead = offer({ sku: 'DEAD', price_usd: 0.1, in_stock: false, stock: 0 })
    const pricey = offer({ sku: 'PRICEY', price_usd: 9 })
    const mouser = offer({ sku: 'M', distributor: 'mouser', price_usd: 1 })
    const lcsc = offer({ sku: 'L', distributor: 'lcsc', price_usd: 1 })
    const out = groupOffersByTier([dead, pricey, mouser, lcsc])
    expect(out.exact.map((o) => o.sku)).toEqual(['L', 'M', 'PRICEY', 'DEAD'])
  })

  test('does not mutate the input array', () => {
    const a = offer({ sku: 'A', price_usd: 5 })
    const b = offer({ sku: 'B', price_usd: 1 })
    const input = [a, b]
    groupOffersByTier(input)
    expect(input.map((o) => o.sku)).toEqual(['A', 'B'])
  })

  test('tolerates a missing offers array', () => {
    expect(groupOffersByTier(undefined)).toEqual({ exact: [], packaging: [] })
  })
})

describe('lcscOffer', () => {
  test('finds the exact-tier LCSC offer', () => {
    const l = offer({ distributor: 'lcsc', sku: 'C1' })
    const part = { offers: [offer({ distributor: 'mouser', sku: 'M1' }), l] }
    expect(lcscOffer(part)).toBe(l)
  })

  test('ignores a packaging-tier LCSC offer', () => {
    const part = { offers: [offer({ distributor: 'lcsc', sku: 'C1', match_tier: 'packaging' })] }
    expect(lcscOffer(part)).toBeNull()
  })

  test('returns null for a part with no LCSC listing', () => {
    expect(lcscOffer({ offers: [offer({ distributor: 'mouser', sku: 'M1' })] })).toBeNull()
  })
})

describe('oldestAsOf', () => {
  test('returns the oldest stamp, never the newest', () => {
    const parts = [
      { as_of: '2026-08-15T10:00:00Z' },
      { as_of: '2026-08-14T09:00:00Z' },
      { as_of: '2026-08-15T11:00:00Z' },
    ]
    expect(oldestAsOf(parts)).toBe('2026-08-14T09:00:00Z')
  })

  test('skips null stamps', () => {
    expect(oldestAsOf([{ as_of: null }, { as_of: '2026-08-15T10:00:00Z' }])).toBe('2026-08-15T10:00:00Z')
  })

  test('returns null for an empty list', () => {
    expect(oldestAsOf([])).toBeNull()
  })
})

describe('label maps', () => {
  test('DigiKey is not rendered as the lowercase enum value', () => {
    expect(DISTRIBUTOR_LABEL.digikey).toBe('DigiKey')
    expect(DISTRIBUTOR_LABEL.lcsc).toBe('LCSC')
    expect(DISTRIBUTOR_LABEL.mouser).toBe('Mouser')
  })

  test('every non-ok, non-disabled state has user-facing copy', () => {
    expect(SOURCE_STATE_COPY.timeout).toBe('timed out')
    expect(SOURCE_STATE_COPY.unavailable).toBe('unavailable')
    expect(SOURCE_STATE_COPY.quota_exhausted).toBe('daily quota used up')
  })
})
