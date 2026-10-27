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
  test('unpublished stock is named, never read as zero', () => {
    // Upstream sends null for a part it has no count for, and 0 for one it
    // has none of. Calling the first OUT OF STOCK would be a claim we lack.
    expect(stockInfo(null).label).toBe('STOCK NOT LISTED')
    expect(stockInfo(undefined).label).toBe('STOCK NOT LISTED')
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

describe('shown currency', () => {
  test('converts for display and goes back to dollars', async () => {
    const { setShownCurrency, fmtUnit, fmtUsd } = await import('./theme.js')
    setShownCurrency('INR', 95)
    expect(fmtPrice(1)).toBe('₹95.00')
    expect(fmtUnit(0.0004)).toBe('₹0.0380')
    expect(fmtUsd(1)).toBe('$1.00')
    setShownCurrency('XYZ', 2)
    expect(fmtPrice(1)).toBe('$1.00')
    setShownCurrency('EUR', 0)
    expect(fmtPrice(1)).toBe('$1.00')
  })
})

describe('contrast', () => {
  const lum = (hex) => {
    const h = hex.length === 4 ? `#${hex[1]}${hex[1]}${hex[2]}${hex[2]}${hex[3]}${hex[3]}` : hex
    const [r, g, b] = [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16) / 255)
      .map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b
  }
  const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05) }

  // Small text needs 4.5:1 (WCAG AA) on both page backgrounds.
  test.each(['ink', 'sub', 'muted', 'alert'])('%s text is readable on paper and page', (k) => {
    expect(ratio(C[k], C.paper)).toBeGreaterThanOrEqual(4.5)
    expect(ratio(C[k], C.bg)).toBeGreaterThanOrEqual(4.5)
  })
  test('white on alert is readable for small labels', () => {
    expect(ratio('#ffffff', C.alert)).toBeGreaterThanOrEqual(4.5)
  })
})
