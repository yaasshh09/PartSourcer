import { renderHook, act } from '@testing-library/react'
import { vi, beforeEach, afterEach, test, expect } from 'vitest'
import { CompareProvider, useCompare, rowLeaders, cleanKeys, compareHref, MAX_COMPARE } from './compare.jsx'

const wrapper = ({ children }) => <CompareProvider>{children}</CompareProvider>
const hook = () => renderHook(() => useCompare(), { wrapper })

beforeEach(() => { localStorage.clear() })
afterEach(() => { vi.restoreAllMocks() })

test('adds, removes and reports membership in pin order', () => {
  const { result } = hook()
  act(() => { result.current.add('B') })
  act(() => { result.current.add('A') })
  expect(result.current.keys).toEqual(['B', 'A'])
  expect(result.current.has('A')).toBe(true)
  act(() => { result.current.remove('B') })
  expect(result.current.keys).toEqual(['A'])
})

test('ignores a duplicate pin', () => {
  const { result } = hook()
  act(() => { result.current.add('A') })
  act(() => { result.current.add('A') })
  expect(result.current.keys).toEqual(['A'])
})

test('stops at four and says it is full', () => {
  const { result } = hook()
  for (const k of ['A', 'B', 'C', 'D', 'E']) act(() => { result.current.add(k) })
  expect(result.current.keys).toEqual(['A', 'B', 'C', 'D'])
  expect(result.current.full).toBe(true)
  expect(MAX_COMPARE).toBe(4)
})

test('clear empties the tray', () => {
  const { result } = hook()
  act(() => { result.current.add('A') })
  act(() => { result.current.clear() })
  expect(result.current.keys).toEqual([])
})

test('survives a reload through localStorage', () => {
  const first = hook()
  act(() => { first.result.current.add('LM358P/NOPB') })
  first.unmount()
  expect(hook().result.current.keys).toEqual(['LM358P/NOPB'])
})

test('stores keys only', () => {
  const { result } = hook()
  act(() => { result.current.add('A') })
  expect(JSON.parse(localStorage.getItem('ps-compare'))).toEqual(['A'])
})

test.each([
  ['not json'],
  ['{"a":1}'],
  [JSON.stringify([1, '', 'x'.repeat(201), 'OK'])],
])('a corrupt stored value %s reads as clean keys', (raw) => {
  localStorage.setItem('ps-compare', raw)
  const keys = hook().result.current.keys
  expect(keys.every((k) => typeof k === 'string' && k && k.length <= 200)).toBe(true)
})

test('blocked storage still works in memory', () => {
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('blocked') })
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('blocked') })
  const { result } = hook()
  act(() => { result.current.add('A') })
  expect(result.current.keys).toEqual(['A'])
})

test('setAll replaces the tray with cleaned keys', () => {
  const { result } = hook()
  act(() => { result.current.add('X') })
  act(() => { result.current.setAll(['A', 'A', 'B', 'C', 'D', 'E']) })
  expect(result.current.keys).toEqual(['A', 'B', 'C', 'D'])
})

test('outside a provider the hook is null', () => {
  expect(renderHook(() => useCompare()).result.current).toBeNull()
})

test('cleanKeys and compareHref', () => {
  expect(cleanKeys(['A', 'A', '', 'B'])).toEqual(['A', 'B'])
  expect(compareHref(['A,1', 'LM358P/NOPB'])).toBe('/compare?k=A%2C1&k=LM358P%2FNOPB')
})

// --- rowLeaders -----------------------------------------------------------------

function part(price, stock, over = {}) {
  return { mpn_key: 'K', cheapest: null, offers: [{ distributor: 'lcsc', sku: 'C1',
    match_tier: 'exact', in_stock: stock > 0, currency: 'USD', price_usd: price, stock, ...over }] }
}

test('marks the lowest price and the most stock', () => {
  const { lowestPrice, mostStock } = rowLeaders([part(0.5, 10), part(0.2, 5), part(0.9, 99)])
  expect([...lowestPrice]).toEqual([1])
  expect([...mostStock]).toEqual([2])
})

test('ties mark every tied part', () => {
  const { lowestPrice, mostStock } = rowLeaders([part(0.2, 7), part(0.2, 7)])
  expect([...lowestPrice]).toEqual([0, 1])
  expect([...mostStock]).toEqual([0, 1])
})

test('an unpriced part never gets the price mark', () => {
  const { lowestPrice } = rowLeaders([part(null, 10), part(0.3, 10), part(0.4, 10)])
  expect([...lowestPrice]).toEqual([1])
})

test('one priced part alone gets no price mark', () => {
  expect(rowLeaders([part(null, 10), part(0.3, 10)]).lowestPrice.size).toBe(0)
})

test('a non-USD price is not compared', () => {
  expect(rowLeaders([part(0.1, 1, { currency: 'EUR' }), part(0.3, 1)]).lowestPrice.size).toBe(0)
})

test('nothing in stock anywhere gets no stock mark', () => {
  expect(rowLeaders([part(0.1, 0), part(0.3, 0)]).mostStock.size).toBe(0)
})

test('parts still loading are left out', () => {
  const { lowestPrice, mostStock } = rowLeaders([null, part(0.3, 5)])
  expect(lowestPrice.size + mostStock.size).toBe(0)
})
