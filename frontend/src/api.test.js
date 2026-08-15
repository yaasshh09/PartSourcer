import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest'
import { search, getPart, getEquivalent, encodeKey, ApiError } from './api.js'

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
