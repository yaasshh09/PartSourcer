export const C = {
  bg: '#fffdf5', yellow: '#ffe14d', orange: '#ff5c38', ink: '#111',
  paper: '#fff', sub: '#6a6858', muted: '#8a8778',
}

export function fmtPrice(p) {
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
