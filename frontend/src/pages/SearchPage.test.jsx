import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter, Routes, Route, Link } from 'react-router-dom'
import { vi, beforeEach, afterEach, test, expect } from 'vitest'
import SearchPage from './SearchPage.jsx'
import * as api from '../api.js'

function renderAt(path = '/') {
  return render(<MemoryRouter initialEntries={[path]}><SearchPage /></MemoryRouter>)
}

beforeEach(() => { vi.restoreAllMocks() })
afterEach(() => { vi.restoreAllMocks() })

test('pre-search shows the empty-state pitch', () => {
  renderAt('/')
  expect(screen.getByText('WHY PARTSOURCER')).toBeInTheDocument()
})

test('bootstraps a search from ?q= and shows results + real as_of', async () => {
  vi.spyOn(api, 'search').mockResolvedValue({
    page: 1,
    results: [{ lcsc: 'C8734', mpn: 'STM32F103C8T6', brand: null, package: 'LQFP-48',
      description: 'ARM MCU', stock: 214596, price_usd: 1.0371, datasheet_url: null,
      as_of: '2026-07-12T07:52:24Z' }],
  })
  renderAt('/?q=STM32')
  await waitFor(() => expect(screen.getByText('STM32F103C8T6')).toBeInTheDocument())
  expect(screen.getByText(/RESULTS — 1 MATCHES/)).toBeInTheDocument()
  expect(screen.getByText(/as of Jul 12, 2026/)).toBeInTheDocument()
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
