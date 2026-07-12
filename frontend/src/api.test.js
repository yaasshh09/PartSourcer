import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest'
import { search, getPart, getEquivalent, ApiError } from './api.js'

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

describe('getPart', () => {
  test('returns the detail json', async () => {
    global.fetch = mockFetchOnce({ body: { lcsc: 'C8734', mpn: 'X' } })
    const out = await getPart('C8734')
    expect(out.lcsc).toBe('C8734')
    expect(global.fetch.mock.calls[0][0]).toContain('/api/part/C8734')
  })
  test('404 throws ApiError with status 404 and detail', async () => {
    global.fetch = mockFetchOnce({ ok: false, status: 404, body: { detail: 'Part C000000 not found' } })
    await expect(getPart('C000000')).rejects.toMatchObject({ status: 404, detail: 'Part C000000 not found' })
  })
})

describe('getEquivalent', () => {
  test('returns original + equivalent', async () => {
    global.fetch = mockFetchOnce({ body: { original: {}, equivalent: null, reason: 'x' } })
    const out = await getEquivalent('C8734')
    expect(out.equivalent).toBeNull()
    expect(global.fetch.mock.calls[0][0]).toContain('/api/part/C8734/equivalent')
  })
})

describe('error mapping', () => {
  test('5xx throws ApiError carrying detail', async () => {
    global.fetch = mockFetchOnce({ ok: false, status: 502, body: { detail: 'jlcsearch unreachable' } })
    await expect(search('x')).rejects.toBeInstanceOf(ApiError)
    await expect(search('x')).rejects.toMatchObject({ status: 502, detail: 'jlcsearch unreachable' })
  })
})
