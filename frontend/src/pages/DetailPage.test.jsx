import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { vi, beforeEach, afterEach, test, expect } from 'vitest'
import DetailPage from './DetailPage.jsx'
import * as api from '../api.js'

function renderPart(lcsc) {
  return render(
    <MemoryRouter initialEntries={[`/part/${lcsc}`]}>
      <Routes><Route path="/part/:lcsc" element={<DetailPage />} /></Routes>
    </MemoryRouter>,
  )
}

const detail = {
  lcsc: 'C25531', mpn: '0402WGJ0103TCE', brand: null, package: '0402',
  description: '', stock: 9360, price_usd: 0.0004, price_breaks: null,
  stock_breakdown: null, is_basic: true, is_preferred: false, datasheet_url: null,
  as_of: '2026-07-12T07:52:24Z',
}

beforeEach(() => { vi.restoreAllMocks() })
afterEach(() => { vi.restoreAllMocks() })

test('renders real header + adapted specs, hides ladder & datasheet', async () => {
  vi.spyOn(api, 'getPart').mockResolvedValue(detail)
  vi.spyOn(api, 'getEquivalent').mockResolvedValue({ original: {}, equivalent: null, reason: 'none' })
  renderPart('C25531')
  await waitFor(() => expect(screen.getByText('0402WGJ0103TCE')).toBeInTheDocument())
  expect(screen.getByText('SPECIFICATIONS')).toBeInTheDocument()
  expect(screen.getByText('9,360 IN STOCK')).toBeInTheDocument()
  expect(screen.queryByText('PRICE BREAKS')).not.toBeInTheDocument()
  expect(screen.queryByText(/DATASHEET/)).not.toBeInTheDocument()
})

test('shows the cheaper-equivalent payoff', async () => {
  vi.spyOn(api, 'getPart').mockResolvedValue(detail)
  vi.spyOn(api, 'getEquivalent').mockResolvedValue({
    original: { price_usd: 0.0004 },
    equivalent: { lcsc: 'C881063', mpn: 'RES-ALT', price_usd: 0.0003, stock: 9360,
      package: '0402', match_reason: 'Same 0402 package, 10 kOhm...', percent_cheaper: 25 },
  })
  renderPart('C25531')
  await waitFor(() => expect(screen.getByText('CHEAPER EQUIVALENT FOUND')).toBeInTheDocument())
  expect(screen.getByText('25%')).toBeInTheDocument()
  expect(screen.getByText(/Same 0402 package/)).toBeInTheDocument()
})

test('honest null-equivalent shows the backend reason', async () => {
  vi.spyOn(api, 'getPart').mockResolvedValue(detail)
  vi.spyOn(api, 'getEquivalent').mockResolvedValue({ original: {}, equivalent: null,
    reason: 'No cheaper in-stock drop-in was found.' })
  renderPart('C25531')
  await waitFor(() => expect(screen.getByText(/WON'T FAKE ONE/)).toBeInTheDocument())
  expect(screen.getByText(/No cheaper in-stock drop-in/)).toBeInTheDocument()
})

test('equivalent lookup failure shows an honest "check unavailable" note, not silence', async () => {
  vi.spyOn(api, 'getPart').mockResolvedValue(detail)
  vi.spyOn(api, 'getEquivalent').mockRejectedValue(new api.ApiError(502, 'jlcsearch unreachable'))
  renderPart('C25531')
  await waitFor(() => expect(screen.getByText('0402WGJ0103TCE')).toBeInTheDocument())
  expect(screen.getByText(/EQUIVALENT CHECK UNAVAILABLE/i)).toBeInTheDocument()
  expect(screen.getByText(/jlcsearch unreachable/)).toBeInTheDocument()
  // must NOT claim we checked and found none
  expect(screen.queryByText(/WON'T FAKE ONE/)).not.toBeInTheDocument()
})

test('COPY does not claim success when the clipboard is unavailable', async () => {
  vi.spyOn(api, 'getPart').mockResolvedValue(detail)
  vi.spyOn(api, 'getEquivalent').mockResolvedValue({ original: {}, equivalent: null, reason: 'none' })
  renderPart('C25531')
  await waitFor(() => expect(screen.getByText('0402WGJ0103TCE')).toBeInTheDocument())
  const orig = Object.getOwnPropertyDescriptor(navigator, 'clipboard')
  Object.defineProperty(navigator, 'clipboard', { value: undefined, configurable: true })
  fireEvent.click(screen.getByText('COPY'))
  expect(screen.queryByText('COPIED ✓')).not.toBeInTheDocument()
  if (orig) Object.defineProperty(navigator, 'clipboard', orig)
  else delete navigator.clipboard
})

test('unknown part shows a 404 state', async () => {
  vi.spyOn(api, 'getPart').mockRejectedValue(new api.ApiError(404, 'Part C000000 not found'))
  vi.spyOn(api, 'getEquivalent').mockRejectedValue(new api.ApiError(404, 'x'))
  renderPart('C000000')
  await waitFor(() => expect(screen.getByText(/not found|isn't on the board/i)).toBeInTheDocument())
})
