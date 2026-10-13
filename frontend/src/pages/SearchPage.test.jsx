import { render, screen, waitFor, fireEvent, act } from '@testing-library/react'
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
  expect(screen.getByText(/SHOWING 1 RESULTS/)).toBeInTheDocument()
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
  const header = screen.getByText(/SHOWING 1 RESULTS/)
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

test('a long wait explains itself instead of just spinning', async () => {
  // The live backend is on a free plan and cold-starts in about 20 seconds.
  // A bare spinner for that long reads as a broken site.
  vi.spyOn(api, 'search').mockReturnValue(new Promise(() => {}))
  vi.useFakeTimers({ shouldAdvanceTime: true })
  try {
    renderAt('/?q=STM32')

    expect(screen.getByText('SEARCHING…')).toBeInTheDocument()
    expect(screen.queryByText(/sleeps when nobody/i)).not.toBeInTheDocument()

    await act(async () => { await vi.advanceTimersByTimeAsync(6000) })

    expect(screen.getByText(/sleeps when nobody/i)).toBeInTheDocument()
  } finally {
    vi.useRealTimers()
  }
})

function priced(key, price) {
  return part({ mpn_key: key, mpn: key, offers: [offer({ sku: key, mpn_as_listed: key, price_usd: price })] })
}

const SORTABLE = { page: 1, query: 'r', sources: OK_SOURCES,
  results: [priced('MID', 0.5), priced('NONE', null), priced('LOW', 0.1), priced('HIGH', 2)] }

function shownOrder() {
  return screen.getAllByRole('link', { name: /^(MID|NONE|LOW|HIGH)$/ }).map((a) => a.textContent)
}

test('keeps the best match order until asked to sort', async () => {
  vi.spyOn(api, 'search').mockResolvedValue(SORTABLE)
  renderAt('/?q=r')
  await waitFor(() => expect(screen.getByText('MID')).toBeInTheDocument())
  expect(shownOrder()).toEqual(['MID', 'NONE', 'LOW', 'HIGH'])
  expect(screen.getByRole('button', { name: /best match/i })).toHaveAttribute('aria-pressed', 'true')
})

test('sorts by price low to high, unpriced last, without searching again', async () => {
  const spy = vi.spyOn(api, 'search').mockResolvedValue(SORTABLE)
  renderAt('/?q=r')
  await waitFor(() => expect(screen.getByText('MID')).toBeInTheDocument())
  fireEvent.click(screen.getByRole('button', { name: /price, low to high/i }))
  expect(shownOrder()).toEqual(['LOW', 'MID', 'HIGH', 'NONE'])
  expect(spy).toHaveBeenCalledTimes(1)
})

test('a shared sorted link opens sorted', async () => {
  vi.spyOn(api, 'search').mockResolvedValue(SORTABLE)
  renderAt('/?q=r&sort=price')
  await waitFor(() => expect(screen.getByText('MID')).toBeInTheDocument())
  expect(shownOrder()).toEqual(['LOW', 'MID', 'HIGH', 'NONE'])
})

test('a new search keeps the price sort', async () => {
  const spy = vi.spyOn(api, 'search').mockResolvedValue(SORTABLE)
  renderAt('/?q=r&sort=price')
  await waitFor(() => expect(screen.getByText('MID')).toBeInTheDocument())
  fireEvent.click(screen.getByRole('button', { name: 'AMS1117' }))
  await waitFor(() => expect(spy).toHaveBeenLastCalledWith('AMS1117'))
  await waitFor(() => expect(screen.getByText('MID')).toBeInTheDocument())
  expect(shownOrder()).toEqual(['LOW', 'MID', 'HIGH', 'NONE'])
})

test('results say the prices leave out shipping', async () => {
  vi.spyOn(api, 'search').mockResolvedValue(SORTABLE)
  renderAt('/?q=r')
  await waitFor(() => expect(screen.getByText('MID')).toBeInTheDocument())
  expect(screen.getByText(/excludes shipping/i)).toBeInTheDocument()
})

test('offers searches that found parts again, newest first', async () => {
  localStorage.clear()
  vi.spyOn(api, 'search').mockResolvedValue({ page: 1, query: 'x', results: [part()], sources: OK_SOURCES })
  const a = renderAt('/?q=NE555')
  await waitFor(() => expect(screen.getByText(/SHOWING 1 RESULTS/)).toBeInTheDocument())
  a.unmount()
  const b = renderAt('/?q=LM358')
  await waitFor(() => expect(screen.getByText(/SHOWING 1 RESULTS/)).toBeInTheDocument())
  b.unmount()
  renderAt('/')
  const recent = screen.getByRole('group', { name: /recent searches/i })
  expect([...recent.querySelectorAll('button')].map((x) => x.textContent)).toEqual(['LM358', 'NE555', 'Clear'])
  fireEvent.click(screen.getByRole('button', { name: 'Clear' }))
  expect(screen.queryByRole('group', { name: /recent searches/i })).toBeNull()
})

test('does not remember a search that found nothing', async () => {
  localStorage.clear()
  vi.spyOn(api, 'search').mockResolvedValue({ page: 1, query: 'x', results: [], sources: OK_SOURCES })
  const a = renderAt('/?q=GHOST')
  await waitFor(() => expect(screen.getByText('NO PARTS FOUND')).toBeInTheDocument())
  a.unmount()
  renderAt('/')
  expect(screen.queryByRole('group', { name: /recent searches/i })).toBeNull()
})

test('an empty result offers a shorter search and the category pages', async () => {
  const spy = vi.spyOn(api, 'search').mockResolvedValue({ page: 1, query: 'x', results: [], sources: OK_SOURCES })
  renderAt('/?q=NE555 timer DIP8')
  await waitFor(() => expect(screen.getByText('NO PARTS FOUND')).toBeInTheDocument())
  expect(screen.getByRole('link', { name: /browse by category/i })).toHaveAttribute('href', '/browse')
  fireEvent.click(screen.getByRole('button', { name: /search "NE555"/i }))
  await waitFor(() => expect(spy).toHaveBeenLastCalledWith('NE555'))
})

const tiered = (key, basic, preferred = false) => part({ mpn_key: key, mpn: key,
  offers: [offer({ sku: `C-${key}`, is_basic: basic, is_preferred: preferred })] })

// JLCPCB charges a setup fee per Extended part, so Basic is worth filtering on.
test('can show only JLC Basic and Preferred parts, and says how many it hid', async () => {
  vi.spyOn(api, 'search').mockResolvedValue({ page: 1, query: 'r', sources: OK_SOURCES,
    results: [tiered('BASIC', true), tiered('EXT', false), tiered('PREF', false, true),
      part({ mpn_key: 'MOUSER', mpn: 'MOUSER', offers: [offer({ distributor: 'mouser', sku: 'M-1' })] })] })
  renderAt('/?q=r')
  await waitFor(() => expect(screen.getByText('BASIC')).toBeInTheDocument())
  fireEvent.click(screen.getByRole('button', { name: /jlc basic only/i }))
  expect(screen.getAllByRole('link', { name: /^(BASIC|EXT|PREF|MOUSER)$/ }).map((a) => a.textContent))
    .toEqual(['BASIC', 'PREF'])
  expect(screen.getByText(/2 of 4 results hidden/i)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /jlc basic only/i })).toHaveAttribute('aria-pressed', 'true')
})

test('a shared Basic only link opens filtered', async () => {
  vi.spyOn(api, 'search').mockResolvedValue({ page: 1, query: 'r', sources: OK_SOURCES,
    results: [tiered('BASIC', true), tiered('EXT', false)] })
  renderAt('/?q=r&basic=1')
  await waitFor(() => expect(screen.getByText('BASIC')).toBeInTheDocument())
  expect(screen.queryByText('EXT')).toBeNull()
})
