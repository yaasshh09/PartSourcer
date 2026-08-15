import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter, Routes, Route, useLocation, useNavigate } from 'react-router-dom'
import { vi, beforeEach, afterEach, test, expect } from 'vitest'
import DetailPage from './DetailPage.jsx'
import * as api from '../api.js'

function LocationProbe() {
  const loc = useLocation()
  return <div data-testid="loc">{loc.pathname}</div>
}

function renderPart(path) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes><Route path="/part/*" element={<><DetailPage /><LocationProbe /></>} /></Routes>
    </MemoryRouter>,
  )
}

function offer(over = {}) {
  return {
    distributor: 'lcsc', sku: 'C25531', mpn_as_listed: '0402WGJ0103TCE',
    match_tier: 'exact', match_note: null, stock: 9360, in_stock: true,
    price_usd: 0.0004, price_breaks: null, currency: 'USD', product_url: null,
    as_of: '2026-08-15T07:52:24Z', is_basic: true, is_preferred: false,
    ...over,
  }
}

function partResponse(over = {}, sources = [{ distributor: 'lcsc', state: 'ok', detail: null, as_of: null }]) {
  return {
    part: {
      mpn_key: '0402WGJ0103TCE', mpn: '0402WGJ0103TCE', brand: null, package: '0402',
      description: '', datasheet_url: null, offers: [offer()], cheapest: null,
      cheapest_unavailable_reason: 'compared 1 of 1 sources, need at least 2 to name a cheapest',
      as_of: '2026-08-15T07:52:24Z',
      ...over,
    },
    sources,
  }
}

const noEquivalent = { original: { mpn_key: '0402WGJ0103TCE', mpn: '0402WGJ0103TCE', package: '0402', price_usd: 0.0004, stock: 9360, lcsc: 'C25531', distributor: 'lcsc' }, equivalent: null, reason: 'none', as_of: '2026-08-15T07:52:24Z' }

const origClipboard = Object.getOwnPropertyDescriptor(navigator, 'clipboard')
function setClipboard(writeText) {
  Object.defineProperty(navigator, 'clipboard', {
    value: writeText ? { writeText } : undefined, configurable: true,
  })
}
afterEach(() => {
  if (origClipboard) Object.defineProperty(navigator, 'clipboard', origClipboard)
  else delete navigator.clipboard
})
beforeEach(() => { vi.restoreAllMocks() })
afterEach(() => { vi.restoreAllMocks() })

test('renders the header and the offer table for the v2 shape', async () => {
  setClipboard(null)
  vi.spyOn(api, 'getPart').mockResolvedValue(partResponse())
  vi.spyOn(api, 'getEquivalent').mockResolvedValue(noEquivalent)
  renderPart('/part/0402WGJ0103TCE')
  await waitFor(() => expect(screen.getByText('0402WGJ0103TCE')).toBeInTheDocument())
  expect(screen.getByText(/EXACT MATCH/i)).toBeInTheDocument()
  expect(screen.getByText('SPECIFICATIONS')).toBeInTheDocument()
  // Once in the header badge, once in the offer table row, so getAllByText.
  expect(screen.getAllByText('9,360 IN STOCK')).toHaveLength(2)
})

test('fetches the splat key verbatim, slash and all', async () => {
  setClipboard(null)
  const getPart = vi.spyOn(api, 'getPart').mockResolvedValue(
    partResponse({ mpn_key: 'LM358P/NOPB', mpn: 'LM358P/NOPB' }))
  vi.spyOn(api, 'getEquivalent').mockResolvedValue(noEquivalent)
  renderPart('/part/LM358P/NOPB')
  await waitFor(() => expect(getPart).toHaveBeenCalledWith('LM358P/NOPB'))
})

test('self-corrects the URL when the backend returns a different canonical key', async () => {
  setClipboard(null)
  vi.spyOn(api, 'getPart').mockResolvedValue(partResponse())
  vi.spyOn(api, 'getEquivalent').mockResolvedValue(noEquivalent)
  renderPart('/part/C25531')
  await waitFor(() => expect(screen.getByTestId('loc')).toHaveTextContent('/part/0402WGJ0103TCE'))
})

test('leaves the URL alone when the key already matches', async () => {
  setClipboard(null)
  vi.spyOn(api, 'getPart').mockResolvedValue(partResponse())
  vi.spyOn(api, 'getEquivalent').mockResolvedValue(noEquivalent)
  renderPart('/part/0402WGJ0103TCE')
  await waitFor(() => expect(screen.getByText('SPECIFICATIONS')).toBeInTheDocument())
  expect(screen.getByTestId('loc')).toHaveTextContent('/part/0402WGJ0103TCE')
})

function BackButton() {
  const navigate = useNavigate()
  return <button type="button" onClick={() => navigate(-1)}>go back</button>
}

// The correction must REPLACE the stale entry, not push over it. With a push,
// Back returns to the legacy key, which redirects forward again and traps the
// user. Asserting the pathname alone cannot tell the two apart, so this walks
// the history instead.
test('self-correcting replaces the stale entry, so Back escapes instead of re-redirecting', async () => {
  setClipboard(null)
  vi.spyOn(api, 'getPart').mockResolvedValue(partResponse())
  vi.spyOn(api, 'getEquivalent').mockResolvedValue(noEquivalent)
  render(
    <MemoryRouter initialEntries={['/', '/part/C25531']} initialIndex={1}>
      <LocationProbe />
      <BackButton />
      <Routes>
        <Route path="/" element={<div>home</div>} />
        <Route path="/part/*" element={<DetailPage />} />
      </Routes>
    </MemoryRouter>,
  )
  await waitFor(() => expect(screen.getByTestId('loc')).toHaveTextContent('/part/0402WGJ0103TCE'))
  fireEvent.click(screen.getByRole('button', { name: 'go back' }))
  await waitFor(() => expect(screen.getByTestId('loc').textContent).toBe('/'))
})

test('warns when a distributor did not answer', async () => {
  setClipboard(null)
  vi.spyOn(api, 'getPart').mockResolvedValue(partResponse({}, [
    { distributor: 'lcsc', state: 'ok', detail: null, as_of: null },
    { distributor: 'mouser', state: 'timeout', detail: 'read timeout', as_of: null },
  ]))
  vi.spyOn(api, 'getEquivalent').mockResolvedValue(noEquivalent)
  renderPart('/part/0402WGJ0103TCE')
  await waitFor(() => expect(screen.getByRole('status')).toBeInTheDocument())
  expect(screen.getByText(/Mouser timed out/)).toBeInTheDocument()
})

test('stays silent about sources when everything answered', async () => {
  setClipboard(null)
  vi.spyOn(api, 'getPart').mockResolvedValue(partResponse())
  vi.spyOn(api, 'getEquivalent').mockResolvedValue(noEquivalent)
  renderPart('/part/0402WGJ0103TCE')
  await waitFor(() => expect(screen.getByText('SPECIFICATIONS')).toBeInTheDocument())
  expect(screen.queryByRole('status')).not.toBeInTheDocument()
})

test('the percent panel compares against original.price_usd, not the headline offer', async () => {
  setClipboard(vi.fn().mockResolvedValue())
  // Mouser at $0.0002 is the cheapest in-stock exact offer, so it is the
  // headline. The matcher compared the LCSC listing at $0.0004, so the arrow
  // must read 0.0004 or it would contradict the 25% the backend computed.
  // These two prices must stay different, or the test proves nothing.
  vi.spyOn(api, 'getPart').mockResolvedValue(partResponse({
    offers: [offer({ distributor: 'mouser', sku: 'M-1', price_usd: 0.0002, is_basic: null }), offer()],
  }))
  vi.spyOn(api, 'getEquivalent').mockResolvedValue({
    original: { mpn_key: '0402WGJ0103TCE', mpn: '0402WGJ0103TCE', package: '0402',
      price_usd: 0.0004, stock: 9360, lcsc: 'C25531', distributor: 'lcsc' },
    equivalent: { mpn_key: 'RES-ALT', lcsc: 'C881063', mpn: 'RES-ALT', price_usd: 0.0003,
      stock: 9360, package: '0402', match_reason: 'Same 0402 package, 10 kOhm...', percent_cheaper: 25 },
    reason: null, as_of: '2026-08-15T07:52:24Z',
  })
  renderPart('/part/0402WGJ0103TCE')
  await waitFor(() => expect(screen.getByText('CHEAPER EQUIVALENT FOUND')).toBeInTheDocument())
  expect(screen.getByText('25%')).toBeInTheDocument()
  expect(screen.getByText('$0.0004 → $0.0003')).toBeInTheDocument()
  expect(screen.getByText(/Same 0402 package/)).toBeInTheDocument()
})

test('the equivalent links to its canonical part page', async () => {
  setClipboard(null)
  vi.spyOn(api, 'getPart').mockResolvedValue(partResponse())
  vi.spyOn(api, 'getEquivalent').mockResolvedValue({
    original: { mpn_key: '0402WGJ0103TCE', mpn: '0402WGJ0103TCE', package: '0402',
      price_usd: 0.0004, stock: 9360, lcsc: 'C25531', distributor: 'lcsc' },
    equivalent: { mpn_key: 'RES-ALT', lcsc: 'C881063', mpn: 'RES-ALT', price_usd: 0.0003,
      stock: 9360, package: '0402', match_reason: 'Same 0402 package', percent_cheaper: 25 },
    reason: null, as_of: '2026-08-15T07:52:24Z',
  })
  renderPart('/part/0402WGJ0103TCE')
  await waitFor(() => expect(screen.getByText('CHEAPER EQUIVALENT FOUND')).toBeInTheDocument())
  expect(screen.getByRole('link', { name: /View the RES-ALT part page/i }))
    .toHaveAttribute('href', '/part/RES-ALT')
})

test('honest null-equivalent shows the backend reason', async () => {
  setClipboard(null)
  vi.spyOn(api, 'getPart').mockResolvedValue(partResponse())
  vi.spyOn(api, 'getEquivalent').mockResolvedValue({
    ...noEquivalent, reason: 'No cheaper in-stock drop-in was found.' })
  renderPart('/part/0402WGJ0103TCE')
  await waitFor(() => expect(screen.getByText(/WON'T FAKE ONE/)).toBeInTheDocument())
  expect(screen.getByText(/No cheaper in-stock drop-in/)).toBeInTheDocument()
})

test('equivalent lookup failure shows an honest "check unavailable" note, not silence', async () => {
  setClipboard(null)
  vi.spyOn(api, 'getPart').mockResolvedValue(partResponse())
  vi.spyOn(api, 'getEquivalent').mockRejectedValue(new api.ApiError(502, 'jlcsearch unreachable'))
  renderPart('/part/0402WGJ0103TCE')
  await waitFor(() => expect(screen.getByText('0402WGJ0103TCE')).toBeInTheDocument())
  expect(screen.getByText(/EQUIVALENT CHECK UNAVAILABLE/i)).toBeInTheDocument()
  expect(screen.getByText(/jlcsearch unreachable/)).toBeInTheDocument()
  expect(screen.queryByText(/WON'T FAKE ONE/)).not.toBeInTheDocument()
})

test('header exposes copy for MPN and the LCSC code, plus distributor links', async () => {
  setClipboard(vi.fn().mockResolvedValue())
  vi.spyOn(api, 'getPart').mockResolvedValue(partResponse())
  vi.spyOn(api, 'getEquivalent').mockResolvedValue(noEquivalent)
  renderPart('/part/0402WGJ0103TCE')
  await waitFor(() => expect(screen.getByText('0402WGJ0103TCE')).toBeInTheDocument())
  expect(screen.getByRole('button', { name: /Copy LCSC code/i })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /Copy MPN/i })).toBeInTheDocument()
  expect(screen.getByRole('link', { name: /^View on LCSC/i }))
    .toHaveAttribute('href', 'https://www.lcsc.com/search?q=C25531')
})

test('a part with no LCSC offer shows no LCSC code row and no LCSC links', async () => {
  setClipboard(vi.fn().mockResolvedValue())
  vi.spyOn(api, 'getPart').mockResolvedValue(partResponse({
    offers: [offer({ distributor: 'mouser', sku: 'M-1', product_url: 'https://mouser.com/p/M1',
      is_basic: null, is_preferred: null })],
  }))
  vi.spyOn(api, 'getEquivalent').mockResolvedValue(noEquivalent)
  renderPart('/part/0402WGJ0103TCE')
  await waitFor(() => expect(screen.getByText('SPECIFICATIONS')).toBeInTheDocument())
  expect(screen.queryByRole('link', { name: /^View on LCSC/i })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /Copy LCSC code/i })).not.toBeInTheDocument()
  // The spec row too: an omitted row, not a row with a blank value.
  expect(screen.queryByText('LCSC')).not.toBeInTheDocument()
})

test('unknown part shows a 404 state', async () => {
  setClipboard(null)
  vi.spyOn(api, 'getPart').mockRejectedValue(new api.ApiError(404, 'Part C000000 not found'))
  vi.spyOn(api, 'getEquivalent').mockRejectedValue(new api.ApiError(404, 'x'))
  renderPart('/part/C000000')
  await waitFor(() => expect(screen.getByText(/not found|isn't on the board/i)).toBeInTheDocument())
})
