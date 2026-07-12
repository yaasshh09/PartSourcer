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
    throw new ApiError(0, 'Network error — is the backend running?')
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

export function search(q, page = 1) {
  return getJson(`/search?q=${encodeURIComponent(q)}&page=${page}`)
}

export function getPart(lcsc) {
  return getJson(`/part/${encodeURIComponent(lcsc)}`)
}

export function getEquivalent(lcsc) {
  return getJson(`/part/${encodeURIComponent(lcsc)}/equivalent`)
}
