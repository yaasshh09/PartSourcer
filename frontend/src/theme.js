// Contrast on paper, measured: ink 18.9, sub 5.6, muted 5.3, alert 5.4. The
// brand orange is 3.1, too faint for small text, so it fills buttons and
// marks while alert carries warnings and errors written in words.
export const C = {
  bg: '#fffdf5', yellow: '#ffe14d', orange: '#ff5c38', ink: '#111',
  paper: '#fff', sub: '#6a6858', muted: '#6f6c5e', alert: '#c2381a',
}

// How wide a page runs before it starts leaving margin, in two tiers. The
// shell carries offer tables and card grids and wants the room. A prose page
// still stops narrower, because the cards inside it hold body text and a line
// that runs the whole monitor is not readable however little space it wastes.
export const SHELL_MAX = 1600
export const PROSE_MAX = 1400

export const ARCHIVO = "'Archivo',sans-serif"
export const MONO = "'IBM Plex Mono',monospace"

// What a missing price is called everywhere it shows. Blank reads as a fetch
// that failed and $0.0000 reads as free, so the gap gets a name.
export const NO_PRICE = 'no price'

// No distributor API quotes shipping or tax, and both depend on where the
// order goes, so every surface that shows a price says what it leaves out.
export const SHIPPING_NOTE = 'Excludes shipping, tax and import duties, which each distributor adds at checkout.'

// Every price arrives in USD. Another currency is a display choice only, set
// once by the currency provider, so the formatters below are the one place a
// conversion happens and nothing that compares or exports prices sees it.
const SYMBOL = { USD: '$', EUR: '€', GBP: '£', INR: '₹' }
let shown = { code: 'USD', rate: 1 }

export function setShownCurrency(code, rate) {
  shown = SYMBOL[code] && rate > 0 ? { code, rate } : { code: 'USD', rate: 1 }
}

function money(usd, fourBelow) {
  const v = usd * shown.rate
  return SYMBOL[shown.code] + (v < fourBelow ? v.toFixed(4) : v.toFixed(2))
}

export function fmtPrice(p) {
  if (p == null) return ''
  return money(p, 0.01)
}

// Four places under a dollar. Rounded to cents, $0.014 shows as $0.01 and
// fifty of them then add up to $0.70, which reads as a wrong sum.
export const fmtUnit = (p) => money(p, 1)

// Always dollars, for text that leaves the page, like a data report.
export function fmtUsd(p) {
  if (p == null) return ''
  return '$' + (p < 0.01 ? p.toFixed(4) : p.toFixed(2))
}

export function stockInfo(stock) {
  const n = Number(stock) || 0
  if (n >= 3000) return { bg: '#38d17a', color: '#062c16', label: n.toLocaleString() + ' IN STOCK' }
  if (n > 0) return { bg: '#ffb02e', color: '#3a2500', label: n.toLocaleString() + ' LOW' }
  return { bg: '#111', color: '#fff', label: 'OUT OF STOCK' }
}

const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
export function fmtAsOf(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (isNaN(d.getTime())) return ''
  const p = (n) => String(n).padStart(2, '0')
  return `${MONTHS[d.getUTCMonth()]} ${d.getUTCDate()}, ${d.getUTCFullYear()} · ${p(d.getUTCHours())}:${p(d.getUTCMinutes())} UTC`
}
