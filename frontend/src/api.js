const API_BASE = import.meta.env.VITE_API_BASE || '/api'

export class ApiError extends Error {
  constructor(status, detail) {
    super(detail || `HTTP ${status}`)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail || `HTTP ${status}`
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
    throw new ApiError(resp.status, detail)
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

export function getPart(mpnKey) {
  return getJson(`/part/${encodeKey(mpnKey)}`)
}

// Moved out from under /part: a greedy path converter on /part would swallow
// a trailing /equivalent as part of the identifier.
export function getEquivalent(mpnKey) {
  return getJson(`/equivalent/${encodeKey(mpnKey)}`)
}
