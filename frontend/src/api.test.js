import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest'
import { search, getPart, getEquivalent, encodeKey, ApiError, browse, getCategories, prefetchPart, _resetPrefetch } from './api.js'

function mockFetchOnce({ ok = true, status = 200, body = {} }) {
  return vi.fn().mockResolvedValue({
    ok, status,
    json: async () => body,
  })
}

beforeEach(() => { vi.restoreAllMocks() })
afterEach(() => { vi.restoreAllMocks() })

describe('search', () => {
  test('calls /api/search with q and page and returns json', async () => {
    global.fetch = mockFetchOnce({ body: { page: 1, results: [] } })
    const out = await search('STM32', 1)
    expect(out).toEqual({ page: 1, results: [] })
    const url = global.fetch.mock.calls[0][0]
    expect(url).toContain('/api/search')
    expect(url).toContain('q=STM32')
    expect(url).toContain('page=1')
  })
})

describe('encodeKey', () => {
  test('preserves slashes so the greedy path converter still matches', () => {
    expect(encodeKey('LM358P/NOPB')).toBe('LM358P/NOPB')
  })

  test('escapes characters that would break the URL', () => {
    expect(encodeKey('A#B')).toBe('A%23B')
    expect(encodeKey('A B')).toBe('A%20B')
    expect(encodeKey('A%B')).toBe('A%25B')
    expect(encodeKey('A?B')).toBe('A%3FB')
  })

  test('treats a percent as a literal character, not as an escape', () => {
    // An MPN that literally contains the three characters %23 has to arrive
    // at the server as those same three characters, so the percent itself
    // gets escaped. Anything else would silently look up a different part.
    expect(encodeKey('A%23B')).toBe('A%2523B')
  })

  test('passes an empty key through without inventing one', () => {
    expect(encodeKey('')).toBe('')
  })
})

describe('getPart', () => {
  test('returns the {part, sources} json', async () => {
    global.fetch = mockFetchOnce({ body: { part: { mpn_key: 'NE555P' }, sources: [] } })
    const out = await getPart('NE555P')
    expect(out.part.mpn_key).toBe('NE555P')
    expect(global.fetch.mock.calls[0][0]).toContain('/api/part/NE555P')
  })

  test('sends a slash-bearing MPN key unescaped', async () => {
    global.fetch = mockFetchOnce({ body: { part: { mpn_key: 'LM358P/NOPB' }, sources: [] } })
    await getPart('LM358P/NOPB')
    expect(global.fetch.mock.calls[0][0]).toContain('/api/part/LM358P/NOPB')
  })

  test('404 throws ApiError with status 404 and detail', async () => {
    global.fetch = mockFetchOnce({ ok: false, status: 404, body: { detail: 'Part C000000 not found' } })
    await expect(getPart('C000000')).rejects.toMatchObject({ status: 404, detail: 'Part C000000 not found' })
  })
})

describe('getEquivalent', () => {
  test('hits /api/equivalent/, not the deleted /api/part/<key>/equivalent', async () => {
    global.fetch = mockFetchOnce({ body: { original: {}, equivalent: null, reason: 'x' } })
    const out = await getEquivalent('NE555P')
    expect(out.equivalent).toBeNull()
    const url = global.fetch.mock.calls[0][0]
    expect(url).toContain('/api/equivalent/NE555P')
    expect(url).not.toContain('/equivalent/NE555P/equivalent')
    expect(url).not.toMatch(/\/api\/part\//)
  })
})

describe('error mapping', () => {
  test('5xx throws ApiError carrying detail', async () => {
    global.fetch = mockFetchOnce({ ok: false, status: 502, body: { detail: 'jlcsearch unreachable' } })
    await expect(search('x')).rejects.toBeInstanceOf(ApiError)
    await expect(search('x')).rejects.toMatchObject({ status: 502, detail: 'jlcsearch unreachable' })
  })

  test('200 with an unparsable body throws ApiError instead of returning null', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true, status: 200,
      json: async () => { throw new SyntaxError('Unexpected token <') },
    })
    await expect(search('x')).rejects.toBeInstanceOf(ApiError)
  })
})

describe('browse', () => {
  test('sends filters exactly as typed', async () => {
    global.fetch = mockFetchOnce({ body: { results: [] } })
    await browse('resistors', { package: '0603', resistance: '4k7' })
    expect(global.fetch.mock.calls[0][0]).toMatch(/\/browse\/resistors\?package=0603&resistance=4k7$/)
  })

  test('sends no query string when there are no filters', async () => {
    global.fetch = mockFetchOnce({ body: { results: [] } })
    await browse('leds')
    expect(global.fetch.mock.calls[0][0]).toMatch(/\/browse\/leds$/)
  })

  test('getCategories reads /browse', async () => {
    global.fetch = mockFetchOnce({ body: { categories: [] } })
    await getCategories()
    expect(global.fetch.mock.calls[0][0]).toMatch(/\/api\/browse$/)
  })

  test('a 422 surfaces its message', async () => {
    global.fetch = mockFetchOnce({ ok: false, status: 422, body: { detail: "'ten' is not a resistance." } })
    await expect(browse('resistors', { resistance: 'ten' }))
      .rejects.toMatchObject({ status: 422, detail: "'ten' is not a resistance." })
  })
})

describe('prefetchPart', () => {
  beforeEach(() => _resetPrefetch())

  test('a hover read is used once by the page that opens next', async () => {
    global.fetch = mockFetchOnce({ body: { part: { mpn_key: 'NE555P' } } })
    prefetchPart('NE555P')
    expect(global.fetch).toHaveBeenCalledTimes(2)
    await getPart('NE555P')
    await getEquivalent('NE555P')
    expect(global.fetch).toHaveBeenCalledTimes(2)
    await getPart('NE555P')
    expect(global.fetch).toHaveBeenCalledTimes(3)
  })

  test('does not prefetch the same part twice', () => {
    global.fetch = mockFetchOnce({ body: {} })
    prefetchPart('NE555P')
    prefetchPart('NE555P')
    expect(global.fetch).toHaveBeenCalledTimes(2)
  })

  // Hovering down a long list must not spend the visitor's rate limit.
  test('stops after a handful of parts a minute', () => {
    global.fetch = mockFetchOnce({ body: {} })
    for (let i = 0; i < 20; i++) prefetchPart(`P${i}`)
    expect(global.fetch).toHaveBeenCalledTimes(16)
  })

  test('an old hover read is not used', async () => {
    vi.useFakeTimers()
    try {
      global.fetch = mockFetchOnce({ body: {} })
      prefetchPart('NE555P')
      vi.advanceTimersByTime(61_000)
      await getPart('NE555P')
      expect(global.fetch).toHaveBeenCalledTimes(3)
    } finally { vi.useRealTimers() }
  })

  test('a failed hover read does not stick', async () => {
    global.fetch = vi.fn().mockRejectedValueOnce(new Error('down')).mockRejectedValueOnce(new Error('down'))
      .mockResolvedValue({ ok: true, status: 200, json: async () => ({ ok: 1 }) })
    prefetchPart('NE555P')
    await new Promise((r) => setTimeout(r, 0))
    expect(await getPart('NE555P')).toEqual({ ok: 1 })
  })
})
