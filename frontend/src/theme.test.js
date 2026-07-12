import { describe, test, expect } from 'vitest'
import { fmtPrice, stockInfo, fmtAsOf, C } from './theme.js'

describe('fmtPrice', () => {
  test('null/undefined -> empty', () => {
    expect(fmtPrice(null)).toBe('')
    expect(fmtPrice(undefined)).toBe('')
  })
  test('sub-cent uses 4dp', () => { expect(fmtPrice(0.0009)).toBe('$0.0009') })
  test('cent+ uses 2dp', () => { expect(fmtPrice(1.0371)).toBe('$1.04') })
  test('exactly 0.01 uses 2dp', () => { expect(fmtPrice(0.01)).toBe('$0.01') })
})

describe('stockInfo', () => {
  test('healthy stock is green IN STOCK', () => {
    const s = stockInfo(214596)
    expect(s.bg).toBe('#38d17a')
    expect(s.label).toBe('214,596 IN STOCK')
  })
  test('low stock is amber LOW', () => {
    const s = stockInfo(500)
    expect(s.bg).toBe('#ffb02e')
    expect(s.label).toBe('500 LOW')
  })
  test('boundary 3000 is IN STOCK', () => { expect(stockInfo(3000).label).toBe('3,000 IN STOCK') })
  test('zero is OUT OF STOCK', () => {
    const s = stockInfo(0)
    expect(s.bg).toBe('#111')
    expect(s.label).toBe('OUT OF STOCK')
  })
})

describe('fmtAsOf', () => {
  test('formats an ISO UTC timestamp', () => {
    expect(fmtAsOf('2026-07-12T07:52:24.276297Z')).toBe('Jul 12, 2026 · 07:52 UTC')
  })
  test('falsy -> empty', () => { expect(fmtAsOf('')).toBe('') })
})

describe('C', () => {
  test('exposes palette tokens', () => {
    expect(C.yellow).toBe('#ffe14d')
    expect(C.orange).toBe('#ff5c38')
    expect(C.ink).toBe('#111')
  })
})
