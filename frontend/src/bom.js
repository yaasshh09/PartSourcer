/**
 * Pure rules for the BOM check: reading a pasted list, pricing a line at its
 * quantity, and adding up only what can actually be bought. No React and no
 * fetch, so every rule here is cheap to test.
 */
import { DISTRIBUTOR_LABEL, precedence } from './offers.js'

// Each line is one part read, and the API allows 60 a minute per visitor. 40
// leaves room for the extra hop a folded part number costs.
export const MAX_LINES = 40

// Names as KiCad, Altium and JLCPCB exports write them, after header() folds
// case, underscores and a trailing "(optional)". LCSC codes read like part
// numbers, since a C-number finds its part the same way.
const MPN_HEADERS = new Set(['mpn', 'part number', 'part no', 'part #', 'manufacturer part number',
  'manufacturer part', 'mfr part number', 'mfr. part number', 'mfr part #', 'mfr. #', 'mfg part number',
  'mfr pn', 'manufacturer part number 1', 'lcsc', 'lcsc part', 'lcsc part #',
  'lcsc part number', 'jlcpcb part #', 'jlcpcb part'])
const QTY_HEADERS = new Set(['qty', 'qty.', 'quantity', 'quantity per pcb', 'qty per board'])
const REF_HEADERS = new Set(['reference', 'references', 'ref', 'designator', 'designators'])
const HEADER_WORDS = new Set([...MPN_HEADERS, ...QTY_HEADERS, ...REF_HEADERS, 'part', 'mfr', 'value',
  'footprint', 'description', 'comment'])

const header = (t) => t.toLowerCase().replace(/[(（][^)）]*[)）]/g, '').replace(/_/g, ' ').trim()
// ponytail: counts "R1-R4" as one; exports that compress ranges also write a Qty column.
const refCount = (t) => (t || '').split(/[\s,;]+/).filter(Boolean).length

const isQty = (t) => /^\d+$/.test(t) && Number(t) > 0

// Splits on the line's own separator, keeping a quoted cell whole, so a
// designator cell like "R1,R2" stays one cell instead of shifting the rest.
function cells(line) {
  const sep = ['\t', ',', ';'].find((s) => line.includes(s))
  if (!sep) return { sep: null, cells: line.split(/\s+/) }
  const out = []
  let cur = ''
  let quoted = false
  for (const ch of line) {
    if (ch === '"') quoted = !quoted
    else if (ch === sep && !quoted) { out.push(cur); cur = '' }
    else cur += ch
  }
  out.push(cur)
  return { sep, cells: out.map((t) => t.trim()) }
}

/**
 * One part per line: a part number and an optional whole-number quantity, in
 * either order, split by tab, comma, semicolon or spaces. A header row naming
 * an MPN column fixes which cells are read from then on, since real exports
 * lead with designators. Without one, the first cell that is not a quantity
 * is the part. A header with no part number column is flagged rather than
 * read by guesswork. # comments are skipped, and a part listed twice adds up. Over
 * the cap is reported, never trimmed.
 */
export function parseBom(text) {
  const byKey = new Map()
  let cols = null
  let missingMpn = false
  const skipped = []
  for (const raw of (text || '').split(/\r?\n/)) {
    const line = raw.trim()
    if (!line || line.startsWith('#')) continue
    const { sep, cells: row } = cells(line)
    const lower = row.map(header)
    if (lower.some((t) => HEADER_WORDS.has(t))) {
      // A bare "Part" is the part number only when nothing more specific is.
      let mpnCol = lower.findIndex((t) => MPN_HEADERS.has(t))
      if (mpnCol < 0) mpnCol = lower.indexOf('part')
      cols = sep && mpnCol >= 0 ? { mpn: mpnCol, qty: lower.findIndex((t) => QTY_HEADERS.has(t)),
        ref: lower.findIndex((t) => REF_HEADERS.has(t)) } : null
      if (sep && mpnCol < 0) missingMpn = true
      continue
    }
    const toks = row.filter(Boolean)
    const mpn = cols && sep ? row[cols.mpn] : toks.find((t) => !isQty(t))
    if (!mpn) { skipped.push(line); continue }
    // With no quantity column, one part per designator is the count.
    const q = !(cols && sep) ? toks.find(isQty)
      : isQty(row[cols.qty] || '') ? row[cols.qty]
        : cols.qty < 0 && cols.ref >= 0 && refCount(row[cols.ref]) ? refCount(row[cols.ref]) : null
    const key = mpn.toUpperCase()
    const prev = byKey.get(key)
    byKey.set(key, { mpn: key, qty: (prev ? prev.qty : 0) + (q ? Number(q) : 1) })
  }
  const lines = [...byKey.values()]
  return { lines, count: lines.length, tooMany: lines.length > MAX_LINES, missingMpn, skipped }
}

/**
 * What one offer costs for a quantity. A published break ladder is used as
 * published; below its first step you are buying the minimum order, and the
 * note says so. With no ladder the listed price is multiplied out, and the
 * note says that too. No price published means null, never zero.
 */
export function priceAt(offer, qty) {
  const breaks = (offer.price_breaks || []).filter((b) => b && b.price_usd != null && b.qty > 0)
    .sort((a, b) => a.qty - b.qty)
  if (breaks.length) {
    if (qty < breaks[0].qty) {
      const b = breaks[0]
      return { unit: b.price_usd, orderQty: b.qty, total: b.price_usd * b.qty, note: `minimum order ${b.qty}` }
    }
    const b = breaks.filter((x) => x.qty <= qty).pop()
    return { unit: b.price_usd, orderQty: qty, total: b.price_usd * qty, note: null }
  }
  if (offer.price_usd == null) return null
  return { unit: offer.price_usd, orderQty: qty, total: offer.price_usd * qty,
    note: 'no quantity breaks published' }
}

/**
 * The offer that fills a line for the least: exact match, USD, priced, and
 * holding at least what you would order. Packaging variants never fill a
 * line, because a reel is not the tube that was asked for.
 */
export function checkLine(part, qty) {
  const usable = ((part && part.offers) || [])
    .filter((o) => o.match_tier === 'exact' && o.currency === 'USD')
  const priced = usable.map((o) => ({ offer: o, ...priceAt(o, qty) })).filter((p) => p.unit != null)
  if (!priced.length) return { state: 'unpriced' }
  const fits = priced.filter((p) => p.offer.in_stock && p.offer.stock >= p.orderQty)
  if (!fits.length) {
    return { state: 'short', bestStock: Math.max(...usable.map((o) => o.stock || 0)) }
  }
  fits.sort((a, b) => (a.total - b.total) || (precedence(a.offer.distributor) - precedence(b.offer.distributor)))
  const best = fits[0]
  return { state: 'ok', offer: best.offer, unit: best.unit, orderQty: best.orderQty,
    total: best.total, note: best.note, as_of: best.offer.as_of,
    thin: best.offer.stock < THIN_STOCK_RATIO * best.orderQty }
}

// Taking over half a shelf is flagged: another buyer's order between the read
// and yours could leave too few. The pick stays the cheapest that fits.
export const THIN_STOCK_RATIO = 2

/** The price note and, when stock is thin, how much of the shelf the order takes. */
export function lineNote(r) {
  const thin = r.thin
    ? `takes ${Math.round((100 * r.orderQty) / r.offer.stock)}% of the ${r.offer.stock.toLocaleString('en-US')} in stock`
    : null
  return [r.note, thin].filter(Boolean).join('; ')
}

/** The total of the lines that can be bought, and a count of every state. */
export function summarize(rows) {
  const counts = {}
  let total = 0
  let asOf = null
  for (const r of rows) {
    counts[r.state] = (counts[r.state] || 0) + 1
    if (r.state !== 'ok') continue
    total += r.total
    // Oldest, not newest: the total is only as fresh as its stalest line.
    if (r.as_of && (!asOf || Date.parse(r.as_of) < Date.parse(asOf))) asOf = r.as_of
  }
  return { total, counts, asOf }
}

export const STATE_LABEL = {
  ok: 'ok', short: 'not enough stock', unpriced: 'no price', missing: 'not found',
  error: 'could not check', loading: 'checking',
}

const cell = (v) => {
  const s = v == null ? '' : String(v)
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
}

/**
 * With swaps, a line that has one is written as the drop-in, so the file can
 * be ordered from as it is. The note names the part it replaces.
 */
export function toCsv(rows, { swaps = false } = {}) {
  const head = ['MPN', 'Qty', 'Status', 'Distributor', 'SKU', 'Unit price USD', 'Order qty',
    'Line total USD', 'Note']
  const body = rows.map((r) => {
    const s = swaps && r.swapResult
    const l = s ? s.swap : r
    const ok = l.state === 'ok'
    const note = [s ? `swap for ${r.mpn}` : null, ok ? lineNote(l) : null].filter(Boolean).join('; ')
    return [s ? s.mpn : r.mpn, r.qty, STATE_LABEL[l.state] || l.state,
      ok ? DISTRIBUTOR_LABEL[l.offer.distributor] || l.offer.distributor : '', ok ? l.offer.sku : '',
      ok ? l.unit : '', ok ? l.orderQty : '', ok ? Math.round(l.total * 10000) / 10000 : '',
      note].map(cell).join(',')
  })
  return [head.join(','), ...body].join('\n') + '\n'
}

/**
 * The list a share link carries. The header keeps an all-digit part number
 * from reading as a quantity, and quantities stay per board.
 */
export function shareList(rows, { swaps = false } = {}) {
  return ['MPN,Qty', ...rows.map((r) => `${swaps && r.swapResult ? r.swapResult.mpn : r.mpn},${r.per}`)]
    .join('\n')
}

// The same 1% bar the equivalent matcher uses, so a rounding wobble is never
// sold as a saving.
const MIN_SAVING = 0.01

/**
 * Prices a drop-in the same way its line was priced: read through /api/part
 * and run through checkLine at the line's quantity. The equivalent endpoint's
 * own saving is at quantity 1, so it is never used here. A short line that
 * the drop-in can fill gets no saving, since the original cannot be bought.
 */
export function compareSwap(row, swapPart) {
  const swap = checkLine(swapPart, row.qty)
  if (swap.state !== 'ok') return null
  const id = { swap, mpn: swapPart.mpn, key: swapPart.mpn_key }
  if (row.state === 'short') return { kind: 'fills', ...id }
  if (row.state !== 'ok') return null
  const saving = row.total - swap.total
  if (saving <= 0 || saving < MIN_SAVING * row.total) return null
  return { kind: 'saves', ...id, saving, pct: Math.round((100 * saving) / row.total) }
}

/** Swap savings and fill costs, kept apart, and the oldest swap read. */
export function summarizeSwaps(rows) {
  const out = { saves: 0, saving: 0, fills: 0, fillCost: 0, asOf: null }
  for (const { swapResult: s } of rows) {
    if (!s) continue
    if (s.kind === 'saves') { out.saves += 1; out.saving += s.saving } else { out.fills += 1; out.fillCost += s.swap.total }
    const at = s.swap.as_of
    if (at && (!out.asOf || Date.parse(at) < Date.parse(out.asOf))) out.asOf = at
  }
  return out
}
