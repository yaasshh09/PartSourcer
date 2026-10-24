const API_BASE = import.meta.env.VITE_API_BASE || '/api'

export class ApiError extends Error {
  constructor(status, detail, retryAfter = null) {
    super(detail || `HTTP ${status}`)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail || `HTTP ${status}`
    this.retryAfter = retryAfter
  }
}

async function getJson(path) {
  let resp
  try {
    resp = await fetch(`${API_BASE}${path}`, { headers: { Accept: 'application/json' } })
  } catch (e) {
    throw new ApiError(0, 'Network error. Is the backend running?')
  }
  let body = null
  try { body = await resp.json() } catch { body = null }
  if (!resp.ok) {
    const detail = body && typeof body.detail === 'string' ? body.detail : `Request failed (HTTP ${resp.status})`
    // Seconds. Cross-origin the header is hidden unless exposed, so callers
    // need their own default. parseFloat, because Number(null) is 0.
    const wait = parseFloat(resp.headers?.get('retry-after'))
    throw new ApiError(resp.status, detail, Number.isFinite(wait) ? wait : null)
  }
  if (body === null) throw new ApiError(resp.status, 'Malformed response from backend')
  return body
}

// Real MPNs contain slashes (LM358P/NOPB) and the backend path converter is
// greedy so they survive. Escaping the slash would still route, but the
// canonical Location the server builds would then disagree with the address
// bar and the page would bounce. Escape everything else.
export function encodeKey(key) {
  return encodeURIComponent(key).replace(/%2F/g, '/')
}

export function search(q, page = 1) {
  return getJson(`/search?q=${encodeURIComponent(q)}&page=${page}`)
}

// Hovering a search result starts the part page's two reads early. Each read
// is handed to the next page that asks for it, once, and only within a
// minute, so a later visit always reads fresh. The budget keeps a mouse run
// down a long list from spending the visitor's 60 requests a minute.
const PREFETCH_TTL_MS = 60_000
const PREFETCH_PARTS_PER_MIN = 8
const prefetched = new Map()
let budget = { start: 0, used: 0 }

export function _resetPrefetch() { prefetched.clear(); budget = { start: 0, used: 0 } }

function takeOrGet(path) {
  const hit = prefetched.get(path)
  prefetched.delete(path)
  return hit && Date.now() - hit.at < PREFETCH_TTL_MS ? hit.promise : getJson(path)
}

export function prefetchPart(mpnKey) {
  const paths = [`/part/${encodeKey(mpnKey)}`, `/equivalent/${encodeKey(mpnKey)}`]
  const now = Date.now()
  if (paths.every((p) => prefetched.has(p) && now - prefetched.get(p).at < PREFETCH_TTL_MS)) return
  if (now - budget.start >= 60_000) budget = { start: now, used: 0 }
  if (budget.used >= PREFETCH_PARTS_PER_MIN) return
  budget.used += 1
  for (const path of paths) {
    const promise = getJson(path)
    promise.catch(() => { if (prefetched.get(path)?.promise === promise) prefetched.delete(path) })
    prefetched.set(path, { at: now, promise })
  }
}

export function getPart(mpnKey) {
  return takeOrGet(`/part/${encodeKey(mpnKey)}`)
}

// Moved out from under /part: a greedy path converter on /part would swallow
// a trailing /equivalent as part of the identifier.
export function getEquivalent(mpnKey) {
  return takeOrGet(`/equivalent/${encodeKey(mpnKey)}`)
}

export function getCategories() {
  return getJson('/browse')
}

// Values go up exactly as typed ("10k", "100n"). The backend owns unit
// conversion, because upstream silently reads "10k" as 10 ohms.
export function browse(slug, params = {}) {
  const qs = new URLSearchParams(params).toString()
  return getJson(`/browse/${encodeURIComponent(slug)}${qs ? `?${qs}` : ''}`)
}

// Nightly LCSC readings for the past year, the most the backend keeps
// asking for. Not prefetched: it sits below the fold and the part page
// renders fine without it.
export function getHistory(mpnKey) {
  return getJson(`/history/${encodeKey(mpnKey)}?days=365`)
}

// A plain link for a feed reader, not a fetch.
export function feedUrl(mpnKey) {
  return `${API_BASE}/feed/${encodeKey(mpnKey)}`
}

// One call for a whole results page. Repeated keys= rather than a joined
// list, because nothing promises an MPN has no commas.
export function getTrends(mpnKeys) {
  return getJson(`/trends?${mpnKeys.map((k) => `keys=${encodeURIComponent(k)}`).join('&')}`)
}

// Part numbers opened here before, for the search box. Never worth an error.
export function getSuggestions(q) {
  return getJson(`/suggest?q=${encodeURIComponent(q)}`)
}

// ECB reference rates from USD, for showing prices in another currency.
export function getFx() {
  return getJson('/fx')
}

// How each distributor answered real requests over the past day.
export function getStatus() {
  return getJson('/status')
}
