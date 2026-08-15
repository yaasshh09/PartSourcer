import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter, Routes, Route, Link } from 'react-router-dom'
import { vi, beforeEach, afterEach, test, expect } from 'vitest'
import SearchPage from './SearchPage.jsx'
import * as api from '../api.js'

function renderAt(path = '/') {
  return render(<MemoryRouter initialEntries={[path]}><SearchPage /></MemoryRouter>)
}

function offer(over = {}) {
  return {
    distributor: 'lcsc', sku: 'C8734', mpn_as_listed: 'STM32F103C8T6',
    match_tier: 'exact', match_note: null, stock: 214596, in_stock: true,
    price_usd: 1.0371, price_breaks: null, currency: 'USD', product_url: null,
    as_of: '2026-08-15T07:52:24Z', is_basic: null, is_preferred: null,
    ...over,
  }
}

function part(over = {}) {
  return {
    mpn_key: 'STM32F103C8T6', mpn: 'STM32F103C8T6', brand: null,
    package: 'LQFP-48(7x7)', description: 'ARM MCU', datasheet_url: null,
    offers: [offer()], cheapest: null,
    cheapest_unavailable_reason: 'compared 1 of 1 sources, need at least 2 to name a cheapest',
    as_of: '2026-08-15T07:52:24Z',
    ...over,
  }
}

const OK_SOURCES = [{ distributor: 'lcsc', state: 'ok', detail: null, as_of: null }]

beforeEach(() => { vi.restoreAllMocks() })
afterEach(() => { vi.restoreAllMocks() })

test('pre-search shows the empty-state pitch', () => {
  renderAt('/')
  expect(screen.getByText('WHY PARTSOURCER')).toBeInTheDocument()
})

test('bootstraps a search from ?q= and shows results + real as_of', async () => {
  vi.spyOn(api, 'search').mockResolvedValue({
    page: 1, query: 'STM32', results: [part()], sources: OK_SOURCES,
  })
  renderAt('/?q=STM32')
  await waitFor(() => expect(screen.getByText('STM32F103C8T6')).toBeInTheDocument())
  expect(screen.getByText(/RESULTS: 1 MATCHES/)).toBeInTheDocument()
  expect(screen.getByText(/as of Aug 15, 2026/)).toBeInTheDocument()
})

test('no-results state when the list is empty', async () => {
  vi.spyOn(api, 'search').mockResolvedValue({ page: 1, results: [] })
  renderAt('/?q=zzz')
  await waitFor(() => expect(screen.getByText('NO PARTS FOUND')).toBeInTheDocument())
})

test('shows an honest error when the API throws', async () => {
  vi.spyOn(api, 'search').mockRejectedValue(new api.ApiError(502, 'jlcsearch unreachable'))
  renderAt('/?q=x')
  await waitFor(() => expect(screen.getByText(/unavailable|unreachable/i)).toBeInTheDocument())
})

test('clears the input text when q is removed from the URL', async () => {
  vi.spyOn(api, 'search').mockResolvedValue({ page: 1, results: [] })
  render(
    <MemoryRouter initialEntries={['/?q=STM32']}>
      <Routes><Route path="/" element={<SearchPage />} /></Routes>
      <Link to="/">go-home</Link>
    </MemoryRouter>,
  )
  const input = await screen.findByPlaceholderText(/Search by MPN/)
  expect(input.value).toBe('STM32')
  fireEvent.click(screen.getByText('go-home'))
  await waitFor(() => expect(input.value).toBe(''))
})

test('shows the oldest as_of across results, never the newest', async () => {
  vi.spyOn(api, 'search').mockResolvedValue({
    page: 1, query: 'stm32', sources: OK_SOURCES,
    // The NEWEST stamp must stay first. Reversed, a first-result read and an
    // oldest read both land on Aug 14 and this test stops discriminating.
    results: [
      part({ mpn_key: 'A', mpn: 'A', as_of: '2026-08-15T10:00:00Z' }),
      part({ mpn_key: 'B', mpn: 'B', as_of: '2026-08-14T09:00:00Z' }),
    ],
  })
  renderAt('/?q=stm32')
  await waitFor(() => expect(screen.getByText(/Aug 14, 2026/)).toBeInTheDocument())
  expect(screen.queryByText(/Aug 15, 2026/)).not.toBeInTheDocument()
})

test('warns above the results when a distributor did not answer', async () => {
  vi.spyOn(api, 'search').mockResolvedValue({
    page: 1, query: 'stm32', results: [part()],
    sources: [
      { distributor: 'lcsc', state: 'ok', detail: null, as_of: null },
      { distributor: 'mouser', state: 'unavailable', detail: null, as_of: null },
    ],
  })
  renderAt('/?q=stm32')
  await waitFor(() => expect(screen.getByRole('status')).toBeInTheDocument())
  expect(screen.getByText(/Mouser unavailable/)).toBeInTheDocument()
  // Above, not merely present. A caveat rendered under the prices is read
  // after the user has already priced the part, which defeats the warning.
  const status = screen.getByRole('status')
  const header = screen.getByText(/RESULTS: 1 MATCHES/)
  expect(status.compareDocumentPosition(header) & Node.DOCUMENT_POSITION_FOLLOWING)
    .toBeTruthy()
})

test('stays silent about sources when everything answered', async () => {
  vi.spyOn(api, 'search').mockResolvedValue({
    page: 1, query: 'stm32', results: [part()], sources: OK_SOURCES,
  })
  renderAt('/?q=stm32')
  await waitFor(() => expect(screen.getByText('STM32F103C8T6')).toBeInTheDocument())
  expect(screen.queryByRole('status')).not.toBeInTheDocument()
})
