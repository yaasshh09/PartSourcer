import { describe, test, expect } from 'vitest'
import { parseBom, priceAt, checkLine, summarize, toCsv, MAX_LINES } from './bom.js'

function offer(over = {}) {
  return {
    distributor: 'mouser', sku: 'M-1', mpn_as_listed: 'X', match_tier: 'exact', match_note: null,
    stock: 1000, in_stock: true, price_usd: 0.1, price_breaks: null, currency: 'USD',
    product_url: null, as_of: '2026-10-11T08:00:00Z', is_basic: null, is_preferred: null, ...over,
  }
}

const part = (offers, over = {}) => ({ mpn_key: 'X', mpn: 'X', offers, cheapest: null,
  as_of: '2026-10-11T08:00:00Z', ...over })

describe('parseBom', () => {
  test('reads MPN and quantity in either order and any separator', () => {
    const { lines } = parseBom('NE555P, 10\n25\tLM358P\nAMS1117-3.3;4\nRC0603FR-0710KL 100')
    expect(lines).toEqual([
      { mpn: 'NE555P', qty: 10 }, { mpn: 'LM358P', qty: 25 },
      { mpn: 'AMS1117-3.3', qty: 4 }, { mpn: 'RC0603FR-0710KL', qty: 100 },
    ])
  })

  test('a line with no quantity means one', () => {
    expect(parseBom('NE555P').lines).toEqual([{ mpn: 'NE555P', qty: 1 }])
  })

  test('skips blank lines, comments and a header row', () => {
    const { lines } = parseBom('MPN,Qty\n\n# power section\nNE555P,2\nPart Number\tQuantity')
    expect(lines).toEqual([{ mpn: 'NE555P', qty: 2 }])
  })

  test('keeps extra columns out of the part number', () => {
    expect(parseBom('NE555P,3,timer for the blinker').lines).toEqual([{ mpn: 'NE555P', qty: 3 }])
  })

  test('the same part twice adds up, whatever its case', () => {
    expect(parseBom('ne555p 2\nNE555P 3').lines).toEqual([{ mpn: 'NE555P', qty: 5 }])
  })

  test('strips quotes a spreadsheet adds', () => {
    expect(parseBom('"NE555P","7"').lines).toEqual([{ mpn: 'NE555P', qty: 7 }])
  })

  // A real export leads with designators, so the first column is not the part.
  test('a header row picks the part number and quantity columns by name', () => {
    const csv = 'Reference,Value,Footprint,Qty,MPN\n"R1,R2",10k,R_0603,2,RC0603FR-0710KL\nU1,NE555,DIP-8,1,NE555P'
    expect(parseBom(csv).lines).toEqual([{ mpn: 'RC0603FR-0710KL', qty: 2 }, { mpn: 'NE555P', qty: 1 }])
  })

  test('works the same for a tab separated paste from a spreadsheet', () => {
    const tsv = 'Designator\tManufacturer Part Number\tQuantity\nC1 C2 C3\tCL10B104KB8NNNC\t3'
    expect(parseBom(tsv).lines).toEqual([{ mpn: 'CL10B104KB8NNNC', qty: 3 }])
  })

  // KiCad's default export has no MPN column. Reading R1 as a part is a guess.
  test('flags a header with no part number column instead of guessing', () => {
    const out = parseBom('Reference,Value,Footprint,Qty\nR1,10k,R_0603,1')
    expect(out.missingMpn).toBe(true)
    expect(parseBom('NE555P 2').missingMpn).toBe(false)
  })

  test('a plain Part column counts when nothing more specific is named', () => {
    expect(parseBom('Part,Qty\nNE555P,2').lines).toEqual([{ mpn: 'NE555P', qty: 2 }])
  })

  test('a row with an empty part number cell is skipped, not guessed', () => {
    expect(parseBom('Ref,MPN,Qty\nJ1,,1\nU1,NE555P,1').lines).toEqual([{ mpn: 'NE555P', qty: 1 }])
  })

  // Cut silently, a long BOM would look fully checked when it was not.
  test('refuses rather than trims a list over the cap', () => {
    const text = Array.from({ length: MAX_LINES + 1 }, (_, i) => `PART${i} 1`).join('\n')
    const out = parseBom(text)
    expect(out.tooMany).toBe(true)
    expect(out.count).toBe(MAX_LINES + 1)
  })
})

describe('priceAt', () => {
  const breaks = [{ qty: 1, price_usd: 0.5 }, { qty: 10, price_usd: 0.3 }, { qty: 100, price_usd: 0.1 }]

  test('uses the largest break not above the quantity', () => {
    expect(priceAt(offer({ price_breaks: breaks }), 25)).toMatchObject({ unit: 0.3, orderQty: 25, note: null })
    expect(priceAt(offer({ price_breaks: breaks }), 100)).toMatchObject({ unit: 0.1, orderQty: 100 })
    expect(priceAt(offer({ price_breaks: breaks }), 9).total).toBeCloseTo(4.5)
  })

  test('below the first break, prices the minimum order and says so', () => {
    const p = priceAt(offer({ price_breaks: [{ qty: 50, price_usd: 0.02 }] }), 10)
    expect(p).toMatchObject({ unit: 0.02, orderQty: 50, note: 'minimum order 50' })
    expect(p.total).toBeCloseTo(1)
  })

  test('without breaks, multiplies the listed price and says so', () => {
    const p = priceAt(offer({ price_usd: 0.25, price_breaks: null }), 4)
    expect(p).toMatchObject({ unit: 0.25, orderQty: 4, note: 'no quantity breaks published' })
    expect(p.total).toBeCloseTo(1)
  })

  test('an unpriced offer has no price, never zero', () => {
    expect(priceAt(offer({ price_usd: null, price_breaks: null }), 4)).toBeNull()
  })
})

describe('checkLine', () => {
  test('picks the offer that fills the line for the least', () => {
    const lcsc = offer({ distributor: 'lcsc', sku: 'C1', price_usd: 0.05, stock: 500 })
    const mouser = offer({ price_breaks: [{ qty: 1, price_usd: 0.2 }, { qty: 100, price_usd: 0.04 }] })
    const out = checkLine(part([lcsc, mouser]), 200)
    expect(out.state).toBe('ok')
    expect(out.offer).toBe(mouser)
    expect(out.total).toBeCloseTo(8)
  })

  test('skips an offer that cannot cover the quantity', () => {
    const small = offer({ distributor: 'lcsc', sku: 'C1', price_usd: 0.01, stock: 5 })
    const big = offer({ price_usd: 0.5, stock: 1000 })
    expect(checkLine(part([small, big]), 10).offer).toBe(big)
  })

  test('short when nothing holds the quantity, with the best stock seen', () => {
    const out = checkLine(part([offer({ stock: 3 }), offer({ sku: 'M-2', stock: 7 })]), 10)
    expect(out).toMatchObject({ state: 'short', bestStock: 7 })
  })

  test('unpriced when no offer published a price', () => {
    expect(checkLine(part([offer({ price_usd: null })]), 1).state).toBe('unpriced')
  })

  // A different physical product (reel versus tube) must not fill the line.
  test('ignores packaging variants and non USD offers', () => {
    const reel = offer({ match_tier: 'packaging', price_usd: 0.01 })
    const eur = offer({ sku: 'E', currency: 'EUR', price_usd: 0.01 })
    expect(checkLine(part([reel, eur]), 1).state).toBe('unpriced')
  })

  test('ties go to the same distributor order the rest of the site uses', () => {
    const m = offer({ distributor: 'mouser', price_usd: 0.1 })
    const l = offer({ distributor: 'lcsc', sku: 'C1', price_usd: 0.1 })
    expect(checkLine(part([m, l]), 1).offer).toBe(l)
  })
})

describe('summarize', () => {
  test('totals only lines that can be bought and counts the rest', () => {
    const rows = [
      { state: 'ok', total: 1.5, as_of: '2026-10-11T08:00:00Z' },
      { state: 'ok', total: 2.25, as_of: '2026-10-11T07:00:00Z' },
      { state: 'short' }, { state: 'missing' }, { state: 'error' }, { state: 'loading' },
    ]
    const s = summarize(rows)
    expect(s.total).toBeCloseTo(3.75)
    expect(s.counts).toMatchObject({ ok: 2, short: 1, missing: 1, error: 1, loading: 1 })
    expect(s.asOf).toBe('2026-10-11T07:00:00Z')
  })
})

describe('toCsv', () => {
  test('one row per line, quoting what needs it', () => {
    const csv = toCsv([
      { mpn: 'NE555P', qty: 2, state: 'ok', offer: { distributor: 'lcsc', sku: 'C1' },
        unit: 0.1, orderQty: 2, total: 0.2, note: null },
      { mpn: 'A,B', qty: 1, state: 'missing' },
    ])
    const rows = csv.trim().split('\n')
    expect(rows[0]).toBe('MPN,Qty,Status,Distributor,SKU,Unit price USD,Order qty,Line total USD,Note')
    expect(rows[1]).toBe('NE555P,2,ok,LCSC,C1,0.1,2,0.2,')
    expect(rows[2]).toBe('"A,B",1,not found,,,,,,')
  })
})
