import { beforeEach, test, expect } from 'vitest'
import { snapshot, loadWatch, saveWatch, toggleWatch, sinceAdded, MAX_WATCH } from './watch.js'

const offer = (over = {}) => ({ distributor: 'lcsc', sku: 'C1', price_usd: 0.01, stock: 5000,
  in_stock: true, currency: 'USD', match_tier: 'exact', as_of: '2026-10-01T00:00:00Z', ...over })
const part = (offers, key = 'R1') => ({ mpn_key: key, mpn: key, offers, as_of: '2026-10-01T00:00:00Z' })

beforeEach(() => { localStorage.clear() })

test('a snapshot keeps the headline offer it was read from', () => {
  const s = snapshot(part([offer()]), '2026-10-02T00:00:00Z')
  expect(s).toEqual({ k: 'R1', mpn: 'R1', distributor: 'lcsc', sku: 'C1', price_usd: 0.01,
    stock: 5000, as_of: '2026-10-01T00:00:00Z', added: '2026-10-02T00:00:00Z' })
})

test('a part with no offers is still watchable, with nothing to compare against', () => {
  const s = snapshot(part([]))
  expect(s.distributor).toBe(null)
  expect(s.price_usd).toBe(null)
})

test('toggling adds to the front and removes on the second press', () => {
  let list = toggleWatch([], part([offer()], 'A'))
  list = toggleWatch(list, part([offer()], 'B'))
  expect(list.map((e) => e.k)).toEqual(['B', 'A'])
  list = toggleWatch(list, part([offer()], 'A'))
  expect(list.map((e) => e.k)).toEqual(['B'])
})

test('the oldest watch falls off past the cap', () => {
  let list = []
  for (let i = 0; i <= MAX_WATCH; i++) list = toggleWatch(list, part([offer()], `P${i}`))
  expect(list).toHaveLength(MAX_WATCH)
  expect(list.some((e) => e.k === 'P0')).toBe(false)
})

test('storage round-trips and survives junk', () => {
  saveWatch([snapshot(part([offer()]))])
  expect(loadWatch().map((e) => e.k)).toEqual(['R1'])
  localStorage.setItem('ps-watch', '{nope')
  expect(loadWatch()).toEqual([])
  localStorage.setItem('ps-watch', JSON.stringify([{ k: 7 }, null, { k: 'ok' }]))
  expect(loadWatch().map((e) => e.k)).toEqual(['ok'])
})

test('changes are read against the same distributor listing, never another one', () => {
  const was = snapshot(part([offer()]))
  const now = part([offer({ price_usd: 0.012, stock: 3000 }), offer({ distributor: 'mouser', sku: 'M1', price_usd: 0.001 })])
  const c = sinceAdded(was, now)
  expect(c.offer.distributor).toBe('lcsc')
  expect(c.priceDelta).toBeCloseTo(0.002)
  expect(c.stockDelta).toBe(-2000)
})

test('a listing that is gone, or a price missing on either side, gives no delta', () => {
  const was = snapshot(part([offer()]))
  expect(sinceAdded(was, part([offer({ sku: 'C2' })])).offer).toBe(null)
  const c = sinceAdded(was, part([offer({ price_usd: null })]))
  expect(c.priceDelta).toBe(null)
  expect(c.stockDelta).toBe(0)
  const blank = snapshot(part([]))
  expect(sinceAdded(blank, part([offer()])).offer).toBe(null)
})
