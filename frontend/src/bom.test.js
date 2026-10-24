import { describe, test, expect } from 'vitest'
import { parseBom, priceAt, checkLine, summarize, toCsv, lineNote, compareSwap, summarizeSwaps, shareList, MAX_LINES,
  lcscFacts, toJlcBom, jlcGaps, summarizeBaskets } from './bom.js'

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
    expect(parseBom(csv).lines).toEqual([{ mpn: 'RC0603FR-0710KL', qty: 2, refs: 'R1,R2' },
      { mpn: 'NE555P', qty: 1, refs: 'U1' }])
  })

  test('works the same for a tab separated paste from a spreadsheet', () => {
    const tsv = 'Designator\tManufacturer Part Number\tQuantity\nC1 C2 C3\tCL10B104KB8NNNC\t3'
    expect(parseBom(tsv).lines).toEqual([{ mpn: 'CL10B104KB8NNNC', qty: 3, refs: 'C1,C2,C3' }])
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
    expect(parseBom('Ref,MPN,Qty\nJ1,,1\nU1,NE555P,1').lines).toEqual([{ mpn: 'NE555P', qty: 1, refs: 'U1' }])
  })

  // Two plain numbers could be a part and a quantity either way round.
  test('reports lines it could not read instead of dropping them quietly', () => {
    const out = parseBom('0039012040 2\nNE555P 1\nRef,MPN,Qty')
    expect(out.lines).toEqual([{ mpn: 'NE555P', qty: 1 }])
    expect(out.skipped).toEqual(['0039012040 2'])
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

  // An order that takes most of a shelf can lose the race to someone else's.
  test('flags a line whose order takes over half the stock', () => {
    expect(checkLine(part([offer({ stock: 150 })]), 100).thin).toBe(true)
    expect(checkLine(part([offer({ stock: 200 })]), 100).thin).toBe(false)
    expect(checkLine(part([offer({ stock: 1000 })]), 100).thin).toBe(false)
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

  test('the note says when an order takes most of the stock', () => {
    const csv = toCsv([{ mpn: 'X', qty: 100, state: 'ok', offer: { distributor: 'lcsc', sku: 'C1', stock: 150 },
      unit: 0.1, orderQty: 100, total: 10, note: null, thin: true }])
    expect(csv.trim().split('\n')[1]).toBe('X,100,ok,LCSC,C1,0.1,100,10,takes 67% of the 150 in stock')
  })
})

describe('lineNote', () => {
  test('joins the price note and the stock warning', () => {
    const r = { state: 'ok', offer: { stock: 150 }, orderQty: 100, note: 'minimum order 100', thin: true }
    expect(lineNote(r)).toBe('minimum order 100; takes 67% of the 150 in stock')
    expect(lineNote({ ...r, thin: false })).toBe('minimum order 100')
    expect(lineNote({ ...r, thin: false, note: null })).toBe('')
  })
})

describe('parseBom reads EDA exports', () => {
  // JLCPCB's assembly BOM has no quantity column, so the designators count it.
  test('JLCPCB format, counted by designators', () => {
    const csv = 'Comment,Designator,Footprint,JLCPCB Part #（optional）\n10k,"R1,R2,R3",0603,C25804\n100n,C1,0402,C1525'
    expect(parseBom(csv).lines).toEqual([{ mpn: 'C25804', qty: 3, refs: 'R1,R2,R3' }, { mpn: 'C1525', qty: 1, refs: 'C1' }])
  })

  test('KiCad with an added part number field', () => {
    const csv = 'Reference,Value,Footprint,Qty,Manufacturer_Part_Number\n"R1, R2",10k,R_0603,2,RC0603FR-0710KL'
    expect(parseBom(csv).lines).toEqual([{ mpn: 'RC0603FR-0710KL', qty: 2, refs: 'R1,R2' }])
  })

  test('KiCad with an LCSC field and no quantity', () => {
    const csv = 'Reference\tValue\tLCSC Part #\nC1 C2\t100n\tC1525'
    expect(parseBom(csv).lines).toEqual([{ mpn: 'C1525', qty: 2, refs: 'C1,C2' }])
  })

  test('Altium default export', () => {
    const csv = '"Comment","Description","Designator","Footprint","LibRef","Quantity","Manufacturer Part Number 1"\n'
      + '"NE555","Timer","U1, U2","DIP8","NE555","2","NE555P"'
    expect(parseBom(csv).lines).toEqual([{ mpn: 'NE555P', qty: 2, refs: 'U1,U2' }])
  })

  test('a header names no part number column, LCSC or otherwise', () => {
    expect(parseBom('Comment,Designator,Footprint\n10k,R1,0603').missingMpn).toBe(true)
  })
})

// A row as the BOM page holds it once its line has been read.
const row = (offers, qty, over = {}) => ({ mpn: 'ORIG', qty, per: qty, ...checkLine(part(offers), qty), ...over })
const swapPart = (offers) => part(offers, { mpn: 'SWAP', mpn_key: 'SWAP-KEY' })

describe('compareSwap', () => {
  test('a drop-in that is cheaper at the line quantity saves the difference', () => {
    const out = compareSwap(row([offer({ price_usd: 0.1 })], 100), swapPart([offer({ price_usd: 0.05 })]))
    expect(out).toMatchObject({ kind: 'saves', mpn: 'SWAP', key: 'SWAP-KEY', pct: 50 })
    expect(out.saving).toBeCloseTo(5)
    expect(out.swap.total).toBeCloseTo(5)
  })

  // The equivalent endpoint compares at quantity 1. The line is bought at 200.
  test('cheaper at one piece but not at the line quantity is no swap', () => {
    const orig = offer({ price_breaks: [{ qty: 1, price_usd: 0.1 }, { qty: 100, price_usd: 0.02 }] })
    const swap = offer({ price_breaks: [{ qty: 1, price_usd: 0.05 }, { qty: 100, price_usd: 0.03 }] })
    expect(compareSwap(row([orig], 200), swapPart([swap]))).toBeNull()
  })

  test('a saving under 1% is not claimed', () => {
    expect(compareSwap(row([offer({ price_usd: 0.1 })], 100), swapPart([offer({ price_usd: 0.0995 })]))).toBeNull()
  })

  test('a drop-in that cannot fill the line is no swap', () => {
    expect(compareSwap(row([offer({ price_usd: 0.1 })], 100),
      swapPart([offer({ price_usd: 0.01, stock: 3 })]))).toBeNull()
  })

  // The original cannot be bought, so there is nothing to subtract from.
  test('a short line that the drop-in fills says so with no saving', () => {
    const out = compareSwap(row([offer({ stock: 3 })], 10), swapPart([offer({ price_usd: 0.2 })]))
    expect(out).toMatchObject({ kind: 'fills', mpn: 'SWAP' })
    expect(out.saving).toBeUndefined()
    expect(out.swap.total).toBeCloseTo(2)
  })

  test('an unpriced original gets nothing', () => {
    expect(compareSwap(row([offer({ price_usd: null })], 10), swapPart([offer()]))).toBeNull()
  })
})

describe('summarizeSwaps', () => {
  test('adds savings and fill costs apart, and keeps the oldest read', () => {
    const rows = [
      { swapResult: { kind: 'saves', saving: 2, swap: { total: 3, as_of: '2026-10-13T09:00:00Z' } } },
      { swapResult: { kind: 'saves', saving: 0.5, swap: { total: 1, as_of: '2026-10-13T08:00:00Z' } } },
      { swapResult: { kind: 'fills', swap: { total: 4, as_of: '2026-10-13T10:00:00Z' } } },
      { swapResult: null }, {},
    ]
    expect(summarizeSwaps(rows)).toEqual({ saves: 2, saving: 2.5, fills: 1, fillCost: 4,
      asOf: '2026-10-13T08:00:00Z' })
  })
})

describe('swap exports', () => {
  const swapped = { ...row([offer({ price_usd: 0.1 })], 100), swapResult:
    compareSwap(row([offer({ price_usd: 0.1 })], 100), swapPart([offer({ distributor: 'lcsc', sku: 'C9', price_usd: 0.05 })])) }
  const plain = { mpn: 'NE555P', qty: 2, per: 1, state: 'missing' }

  test('the CSV with swaps writes the drop-in in place of the original', () => {
    const lines = toCsv([swapped, plain], { swaps: true }).trim().split('\n')
    expect(lines[1]).toBe('SWAP,100,ok,LCSC,C9,0.05,100,5,swap for ORIG; no quantity breaks published')
    expect(lines[2]).toBe('NE555P,2,not found,,,,,,')
  })

  test('the plain CSV ignores swaps', () => {
    expect(toCsv([swapped]).trim().split('\n')[1]).toMatch(/^ORIG,100,ok,Mouser/)
  })

  test('the share list keeps per board quantities, with or without swaps', () => {
    expect(shareList([swapped, plain])).toBe('MPN,Qty\nORIG,100\nNE555P,1')
    expect(shareList([swapped, plain], { swaps: true })).toBe('MPN,Qty\nSWAP,100\nNE555P,1')
  })
})

describe('JLCPCB assembly BOM', () => {
  test('a part listed twice keeps both sets of designators', () => {
    const csv = 'Designator,MPN\nR1,RC0603FR-0710KL\n"R2, R3",rc0603fr-0710kl'
    expect(parseBom(csv).lines).toEqual([{ mpn: 'RC0603FR-0710KL', qty: 3, refs: 'R1,R2,R3' }])
  })

  test('reads the LCSC code, Basic flag and package off a part', () => {
    const p = part([offer(), offer({ distributor: 'lcsc', sku: 'C25804', is_basic: false })], { package: '0603' })
    expect(lcscFacts(p)).toEqual({ lcsc: 'C25804', basic: false, pkg: '0603' })
  })

  test('a packaging variant on LCSC is not the part that was asked for', () => {
    const p = part([offer({ distributor: 'lcsc', sku: 'C9', match_tier: 'packaging' })], { package: '0603' })
    expect(lcscFacts(p)).toEqual({ lcsc: null, basic: null, pkg: '0603' })
  })

  test('writes the columns JLCPCB asks for, one row per line', () => {
    const rows = [
      { mpn: 'RC0603FR-0710KL', refs: 'R1,R2', lcsc: 'C25804', pkg: '0603', state: 'ok' },
      { mpn: 'NOPE-1', refs: '', lcsc: null, pkg: null, state: 'missing' },
    ]
    expect(toJlcBom(rows)).toBe('Comment,Designator,Footprint,JLCPCB Part #\n'
      + 'RC0603FR-0710KL,"R1,R2",0603,C25804\n'
      + 'NOPE-1,,,\n')
  })

  test('the file reads back in as the same lines', () => {
    const rows = [{ mpn: 'RC0603FR-0710KL', refs: 'R1,R2', lcsc: 'C25804', pkg: '0603' }]
    expect(parseBom(toJlcBom(rows)).lines).toEqual([{ mpn: 'C25804', qty: 2, refs: 'R1,R2' }])
  })

  test('counts what JLCPCB will ask about', () => {
    const rows = [
      { lcsc: 'C1', basic: false, refs: 'R1' }, { lcsc: 'C2', basic: true, refs: 'R2' },
      { lcsc: 'C3', basic: false, refs: '' }, { lcsc: null, basic: null, refs: 'U1' },
    ]
    expect(jlcGaps(rows)).toEqual({ extended: 2, noCode: 1, noRefs: 1 })
  })
})

describe('one distributor or a split order', () => {
  test('a checked line keeps what each distributor would charge for it', () => {
    const lcsc = offer({ distributor: 'lcsc', sku: 'C1', price_usd: 0.05, stock: 500 })
    const mouser = offer({ price_breaks: [{ qty: 1, price_usd: 0.2 }, { qty: 100, price_usd: 0.04 }] })
    const short = offer({ distributor: 'digikey', sku: 'D1', price_usd: 0.01, stock: 5 })
    const out = checkLine(part([lcsc, mouser, short]), 200)
    expect(out.byDist.lcsc).toBeCloseTo(10)
    expect(out.byDist.mouser).toBeCloseTo(8)
    expect(out.byDist.digikey).toBeUndefined()   // cannot fill the line
  })

  test('totals each distributor over the lines it can fill', () => {
    const rows = [
      { state: 'ok', byDist: { lcsc: 1, mouser: 2 } },
      { state: 'ok', byDist: { lcsc: 3 } },
      { state: 'short' },
    ]
    expect(summarizeBaskets(rows)).toEqual({
      lines: 2,
      baskets: [{ distributor: 'lcsc', total: 4, covered: 2 }, { distributor: 'mouser', total: 2, covered: 1 }],
      best: { distributor: 'lcsc', total: 4, covered: 2 },
    })
  })

  test('no single distributor when none can fill every line', () => {
    const rows = [{ state: 'ok', byDist: { lcsc: 1 } }, { state: 'ok', byDist: { mouser: 2 } }]
    expect(summarizeBaskets(rows).best).toBeNull()
  })

  test('the cheapest full basket wins, not the one listed first', () => {
    const rows = [{ state: 'ok', byDist: { lcsc: 5, mouser: 2 } }, { state: 'ok', byDist: { lcsc: 1, mouser: 2 } }]
    expect(summarizeBaskets(rows).best).toEqual({ distributor: 'mouser', total: 4, covered: 2 })
  })
})

// kicad/partsourcer/bom.py writes exactly this. Kept here so the two cannot drift.
test('reads the list the KiCad plugin sends, designators and all', () => {
  expect(parseBom('MPN,Qty,Designator\nR10K,2,"R1,R2"\nC8734,1,"U1"').lines).toEqual([
    { mpn: 'R10K', qty: 2, refs: 'R1,R2' }, { mpn: 'C8734', qty: 1, refs: 'U1' }])
})
