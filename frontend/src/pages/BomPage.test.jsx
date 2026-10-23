import { act, render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { vi, beforeEach, afterEach, test, expect } from 'vitest'
import BomPage from './BomPage.jsx'
import * as api from '../api.js'
import { MAX_LINES } from '../bom.js'

function offer(over = {}) {
  return { distributor: 'lcsc', sku: 'C1', mpn_as_listed: 'X', match_tier: 'exact', match_note: null,
    stock: 1000, in_stock: true, price_usd: 0.1, price_breaks: null, currency: 'USD',
    product_url: 'https://example.com/p', as_of: '2026-10-11T08:00:00Z', is_basic: null,
    is_preferred: null, ...over }
}

const part = (key, offers) => ({ mpn_key: key, mpn: key, brand: null, package: '', description: '',
  datasheet_url: null, offers, cheapest: null, cheapest_unavailable_reason: null,
  as_of: '2026-10-11T08:00:00Z' })

const PARTS = {
  NE555P: part('NE555P', [offer()]),
  TINY: part('TINY', [offer({ sku: 'C2', stock: 2 })]),
  EXT: { ...part('EXT', [offer({ sku: 'C77', is_basic: false })]), package: '0603' },
}

function mockParts(failing = {}) {
  return vi.spyOn(api, 'getPart').mockImplementation((k) => {
    if (failing[k]) return Promise.reject(failing[k])
    if (PARTS[k]) return Promise.resolve({ part: PARTS[k], sources: [] })
    return Promise.reject(new api.ApiError(404, `Part ${k} not found`))
  })
}

const renderPage = (path = '/bom') => render(<MemoryRouter initialEntries={[path]}><BomPage /></MemoryRouter>)

function check(text) {
  fireEvent.change(screen.getByLabelText(/parts list/i), { target: { value: text } })
  fireEvent.click(screen.getByRole('button', { name: /check prices/i }))
}

beforeEach(() => { localStorage.clear(); vi.restoreAllMocks() })
afterEach(() => { vi.restoreAllMocks() })

test('starts with an empty list and a way to try an example', () => {
  renderPage()
  expect(screen.getByLabelText(/parts list/i)).toHaveValue('')
  fireEvent.click(screen.getByRole('button', { name: /try an example/i }))
  expect(screen.getByLabelText(/parts list/i).value).not.toBe('')
})

test('prices each line at its quantity and totals only what can be ordered', async () => {
  const spy = mockParts()
  renderPage()
  check('NE555P 5\nTINY 10\nGHOST 1')
  await waitFor(() => expect(screen.getByText(/1 of 3 lines can be ordered/i)).toBeInTheDocument())
  expect(spy).toHaveBeenCalledTimes(3)
  expect(screen.getByTestId('bom-total')).toHaveTextContent('$0.50')
  expect(screen.getAllByText(/not enough stock/i).length).toBeGreaterThan(0)
  expect(screen.getAllByText(/not found/i).length).toBeGreaterThan(0)
  expect(screen.getByText(/no quantity breaks published/i)).toBeInTheDocument()
  expect(screen.getByText(/excludes shipping/i)).toBeInTheDocument()
})

// Only a backend claim that passed its gates may say cheapest.
test('never calls a pick the cheapest', async () => {
  mockParts()
  const { container } = renderPage()
  check('NE555P 5')
  await waitFor(() => expect(screen.getByTestId('bom-total')).toBeInTheDocument())
  expect(container.textContent).not.toMatch(/cheapest/i)
})

test('refuses a list over the cap instead of checking part of it', () => {
  const spy = mockParts()
  renderPage()
  check(Array.from({ length: MAX_LINES + 1 }, (_, i) => `PART${i} 1`).join('\n'))
  expect(screen.getByText(new RegExp(`up to ${MAX_LINES}`))).toBeInTheDocument()
  expect(spy).not.toHaveBeenCalled()
})

test('retry re-reads only the lines that failed', async () => {
  const spy = mockParts({ NE555P: new api.ApiError(429, 'Too many requests') })
  renderPage()
  check('NE555P 1\nTINY 1')
  await waitFor(() => expect(screen.getAllByText(/could not check/i).length).toBeGreaterThan(0))
  spy.mockImplementation((k) => Promise.resolve({ part: PARTS[k], sources: [] }))
  spy.mockClear()
  fireEvent.click(screen.getByRole('button', { name: /retry failed lines/i }))
  await waitFor(() => expect(screen.getByText(/2 of 2 lines can be ordered/i)).toBeInTheDocument())
  expect(spy).toHaveBeenCalledTimes(1)
  expect(spy).toHaveBeenCalledWith('NE555P')
})

test('keeps the pasted list for next time', () => {
  const first = renderPage()
  fireEvent.change(screen.getByLabelText(/parts list/i), { target: { value: 'NE555P 3' } })
  first.unmount()
  renderPage()
  expect(screen.getByLabelText(/parts list/i)).toHaveValue('NE555P 3')
})

// Rounded to cents, a $0.014 part times 50 would show $0.01 and $0.70.
test('shows unit prices precisely enough to multiply out', async () => {
  PARTS.TENTH = part('TENTH', [offer({ sku: 'C9', price_usd: 0.014 })])
  mockParts()
  renderPage()
  check('TENTH 50')
  await waitFor(() => expect(screen.getByText('$0.0140')).toBeInTheDocument())
  expect(screen.getByTestId('bom-total')).toHaveTextContent('$0.70')
})

test('says so when a pasted header has no part number column', () => {
  const spy = mockParts()
  renderPage()
  check('Reference,Value,Footprint,Qty\nR1,10k,R_0603,1')
  expect(screen.getByRole('alert')).toHaveTextContent(/no part number column/i)
  expect(spy).not.toHaveBeenCalled()
})

test('loads a CSV file into the list', async () => {
  renderPage()
  const file = new File(['MPN,Qty\nNE555P,4\n'], 'bom.csv', { type: 'text/csv' })
  // Every current browser has File.text(); jsdom does not.
  file.text = () => Promise.resolve('MPN,Qty\nNE555P,4\n')
  fireEvent.change(screen.getByLabelText(/load a csv/i), { target: { files: [file] } })
  await waitFor(() => expect(screen.getByLabelText(/parts list/i)).toHaveValue('MPN,Qty\nNE555P,4\n'))
})

// A shared link has to show the prices, not a box the receiver must submit.
test('a shared link fills the list and checks it straight away', async () => {
  const spy = mockParts()
  renderPage(`/bom?list=${encodeURIComponent('MPN,Qty\nNE555P,5')}`)
  expect(screen.getByLabelText(/parts list/i)).toHaveValue('MPN,Qty\nNE555P,5')
  await waitFor(() => expect(screen.getByText(/1 of 1 lines can be ordered/i)).toBeInTheDocument())
  expect(spy).toHaveBeenCalledWith('NE555P')
})

test('copies a link that carries the checked lines', async () => {
  mockParts()
  const orig = Object.getOwnPropertyDescriptor(navigator, 'clipboard')
  const writeText = vi.fn(() => Promise.resolve())
  Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
  try {
    renderPage()
    check('Ref,MPN,Qty\nU1,NE555P,5\nJ1,0039012040,2')
    await waitFor(() => expect(screen.getByRole('button', { name: /copy link/i })).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /copy link/i }))
    const url = new URL(writeText.mock.calls[0][0])
    expect(url.pathname).toBe('/bom')
    // Designators are gone, and the header keeps an all-digit part number
    // from reading as a quantity when the link is opened.
    expect(url.searchParams.get('list')).toBe('MPN,Qty\nNE555P,5\n0039012040,2')
    await waitFor(() => expect(screen.getByRole('button', { name: /link copied/i })).toBeInTheDocument())
  } finally {
    if (orig) Object.defineProperty(navigator, 'clipboard', orig)
    else delete navigator.clipboard
  }
})

test('says which lines were skipped and still checks the rest', async () => {
  const spy = mockParts()
  renderPage()
  check('0039012040 2\nNE555P 1')
  expect(screen.getByRole('status')).toHaveTextContent(/skipped 1 line/i)
  expect(screen.getByRole('status')).toHaveTextContent('0039012040 2')
  await waitFor(() => expect(screen.getByText(/1 of 1 lines can be ordered/i)).toBeInTheDocument())
  expect(spy).toHaveBeenCalledTimes(1)
})

test('a checked part links to its page at the line quantity', async () => {
  mockParts()
  renderPage()
  check('NE555P 5')
  await waitFor(() => expect(screen.getByRole('link', { name: 'NE555P' }))
    .toHaveAttribute('href', '/part/NE555P?qty=5'))
})

test('a board count multiplies every line before it is priced', async () => {
  const spy = mockParts()
  renderPage()
  fireEvent.change(screen.getByLabelText(/boards/i), { target: { value: '3' } })
  check('NE555P 5')
  await waitFor(() => expect(screen.getByText(/1 of 1 lines can be ordered/i)).toBeInTheDocument())
  expect(spy).toHaveBeenCalledWith('NE555P')
  expect(screen.getByText('15')).toBeInTheDocument()
  expect(screen.getByTestId('bom-total')).toHaveTextContent('$1.50')
  expect(screen.getByRole('link', { name: 'NE555P' })).toHaveAttribute('href', '/part/NE555P?qty=15')
})

test('a shared link keeps the per board list and the board count apart', async () => {
  mockParts()
  const orig = Object.getOwnPropertyDescriptor(navigator, 'clipboard')
  const writeText = vi.fn(() => Promise.resolve())
  Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
  try {
    renderPage()
    fireEvent.change(screen.getByLabelText(/boards/i), { target: { value: '4' } })
    check('NE555P 5')
    await waitFor(() => expect(screen.getByRole('button', { name: /copy link/i })).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /copy link/i }))
    const url = new URL(writeText.mock.calls[0][0])
    expect(url.searchParams.get('list')).toBe('MPN,Qty\nNE555P,5')
    expect(url.searchParams.get('boards')).toBe('4')
    await waitFor(() => expect(screen.getByRole('button', { name: /link copied/i })).toBeInTheDocument())
  } finally {
    if (orig) Object.defineProperty(navigator, 'clipboard', orig)
    else delete navigator.clipboard
  }
})

test('opening a shared link with a board count prices at that count', async () => {
  mockParts()
  renderPage(`/bom?list=${encodeURIComponent('MPN,Qty\nNE555P,5')}&boards=2`)
  expect(screen.getByLabelText(/boards/i)).toHaveValue(2)
  await waitFor(() => expect(screen.getByTestId('bom-total')).toHaveTextContent('$1.00'))
})

test('warns when an order takes most of what is in stock', async () => {
  PARTS.THIN = part('THIN', [offer({ sku: 'C7', stock: 150 })])
  mockParts()
  renderPage()
  check('THIN 100')
  await waitFor(() => expect(screen.getByText(/takes 67% of the 150 in stock/i)).toBeInTheDocument())
})

// R10K has a verified drop-in at half the price; CAP has none.
PARTS.R10K = part('R10K', [offer({ sku: 'C10', price_usd: 0.1 })])
PARTS['R10K-ALT'] = part('R10K-ALT', [offer({ sku: 'C11', price_usd: 0.05, as_of: '2026-10-13T09:00:00Z' })])
PARTS.CAP = part('CAP', [offer({ sku: 'C20', price_usd: 0.1 })])
const EQUIV = { R10K: 'R10K-ALT' }

function mockEquivalents(failing = {}) {
  return vi.spyOn(api, 'getEquivalent').mockImplementation((k) => {
    if (failing[k]) return Promise.reject(failing[k])
    const to = EQUIV[k]
    return Promise.resolve({ original: {}, equivalent: to ? { mpn_key: to } : null, reason: 'x' })
  })
}

async function checkThenSwap(text) {
  check(text)
  await waitFor(() => expect(screen.getByRole('button', { name: /find cheaper swaps/i })).toBeInTheDocument())
  fireEvent.click(screen.getByRole('button', { name: /find cheaper swaps/i }))
}

function withClipboard(fn) {
  const orig = Object.getOwnPropertyDescriptor(navigator, 'clipboard')
  const writeText = vi.fn(() => Promise.resolve())
  Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
  return fn(writeText).finally(() => {
    if (orig) Object.defineProperty(navigator, 'clipboard', orig)
    else delete navigator.clipboard
  })
}

test('swaps are offered only once a check has finished, and cost nothing before', async () => {
  mockParts()
  const eq = mockEquivalents()
  renderPage()
  expect(screen.queryByRole('button', { name: /find cheaper swaps/i })).not.toBeInTheDocument()
  check('R10K 100')
  await waitFor(() => expect(screen.getByRole('button', { name: /find cheaper swaps/i })).toBeInTheDocument())
  expect(eq).not.toHaveBeenCalled()
})

test('a found swap shows its saving at the line quantity and a board summary', async () => {
  const parts = mockParts()
  mockEquivalents()
  renderPage()
  await checkThenSwap('R10K 100\nCAP 10')
  await waitFor(() => expect(screen.getByText(/1 swap saves \$5\.00 \(45%\) on this board/i)).toBeInTheDocument())
  expect(screen.getByText(/saves \$5\.00 \(50%\)/i)).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'R10K-ALT' })).toHaveAttribute('href', '/part/R10K-ALT?qty=100')
  expect(screen.getByText(/resistors and capacitors only/i)).toBeInTheDocument()
  // The drop-in is read the same way the line was, not taken from the equivalent's quote.
  expect(parts).toHaveBeenCalledWith('R10K-ALT')
  // CAP had no drop-in and says nothing; the main total stays on the original parts.
  expect(screen.queryByText(/swap check failed/i)).not.toBeInTheDocument()
  expect(screen.getByTestId('bom-total')).toHaveTextContent('$11.00')
})

test('a failed swap lookup says so on its line', async () => {
  mockParts()
  mockEquivalents({ CAP: new api.ApiError(502, 'upstream down') })
  renderPage()
  await checkThenSwap('CAP 10')
  await waitFor(() => expect(screen.getByText(/swap check failed/i)).toBeInTheDocument())
  expect(screen.getByRole('button', { name: /retry swap checks/i })).toBeInTheDocument()
})

test('nothing found says so plainly', async () => {
  mockParts()
  mockEquivalents()
  renderPage()
  await checkThenSwap('CAP 10')
  await waitFor(() => expect(screen.getByText(/no verified cheaper drop-ins/i)).toBeInTheDocument())
})

test('a 429 waits as long as the server asks, then tries that line again', async () => {
  mockParts()
  const eq = mockEquivalents()
  eq.mockImplementationOnce(() => Promise.reject(new api.ApiError(429, 'slow down', 3)))
  renderPage()
  check('R10K 100')
  await waitFor(() => expect(screen.getByRole('button', { name: /find cheaper swaps/i })).toBeInTheDocument())
  vi.useFakeTimers({ shouldAdvanceTime: true })
  try {
    fireEvent.click(screen.getByRole('button', { name: /find cheaper swaps/i }))
    await act(() => vi.advanceTimersByTimeAsync(2000))
    expect(eq).toHaveBeenCalledTimes(1)
    await act(() => vi.advanceTimersByTimeAsync(1500))
    // Anchored: with one line, the board summary also reads 50%.
    await waitFor(() => expect(screen.getByText(/^saves \$5\.00 \(50%\)/i)).toBeInTheDocument())
    expect(eq).toHaveBeenCalledTimes(2)
  } finally {
    vi.useRealTimers()
  }
})

test('the link with swaps carries the drop-in part numbers', async () => {
  mockParts()
  mockEquivalents()
  await withClipboard(async (writeText) => {
    renderPage()
    await checkThenSwap('R10K 100\nCAP 10')
    await waitFor(() => expect(screen.getByRole('button', { name: /copy link with swaps/i })).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /copy link with swaps/i }))
    expect(new URL(writeText.mock.calls[0][0]).searchParams.get('list')).toBe('MPN,Qty\nR10K-ALT,100\nCAP,10')
    await waitFor(() => expect(screen.getByRole('button', { name: /link copied/i })).toBeInTheDocument())
  })
})

test('the CSV with swaps carries the drop-in part numbers', async () => {
  mockParts()
  mockEquivalents()
  const blobs = []
  // jsdom has no object URLs at all, so there is nothing to spy on.
  const saved = [URL.createObjectURL, URL.revokeObjectURL]
  URL.createObjectURL = (b) => { blobs.push(b); return 'blob:x' }
  URL.revokeObjectURL = () => {}
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
  try {
    renderPage()
    await checkThenSwap('R10K 100\nCAP 10')
    await waitFor(() => expect(screen.getByRole('button', { name: /download csv with swaps/i })).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /download csv with swaps/i }))
    const csv = await new Promise((ok) => {
      const fr = new FileReader()
      fr.onload = () => ok(fr.result)
      fr.readAsText(blobs[0])
    })
    expect(csv).toMatch(/^R10K-ALT,100,ok,LCSC,C11,0\.05,100,5,swap for R10K/m)
    expect(csv).toMatch(/^CAP,10,ok/m)
    // The page revokes its URL a tick later.
    await new Promise((r) => setTimeout(r, 0))
  } finally {
    [URL.createObjectURL, URL.revokeObjectURL] = saved
  }
})

test('a new check drops a swap pass that is still running', async () => {
  mockParts()
  let release
  vi.spyOn(api, 'getEquivalent').mockImplementation(() => new Promise((ok) => { release = ok }))
  renderPage()
  await checkThenSwap('R10K 100')
  await waitFor(() => expect(screen.getByText(/checking swaps 0 of 1/i)).toBeInTheDocument())
  check('CAP 10')
  await waitFor(() => expect(screen.getByText(/1 of 1 lines can be ordered/i)).toBeInTheDocument())
  release({ original: {}, equivalent: { mpn_key: 'R10K-ALT' }, reason: 'x' })
  await new Promise((r) => setTimeout(r, 20))
  expect(screen.queryByText(/R10K-ALT/)).not.toBeInTheDocument()
  expect(screen.queryByText(/checking swaps/i)).not.toBeInTheDocument()
})

test('downloads a JLCPCB assembly BOM and says what JLCPCB will ask about', async () => {
  mockParts()
  const blobs = []
  const saved = [URL.createObjectURL, URL.revokeObjectURL]
  URL.createObjectURL = (b) => { blobs.push(b); return 'blob:x' }
  URL.revokeObjectURL = () => {}
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
  try {
    renderPage()
    check('Designator,MPN\n"R1,R2",EXT\nU1,GHOST')
    await waitFor(() => expect(screen.getByText(/0 of 2 lines|1 of 2 lines/i)).toBeInTheDocument())
    expect(screen.getByText(/1 extended part/i)).toBeInTheDocument()
    expect(screen.getByText(/1 line has no LCSC code/i)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /download jlcpcb bom/i }))
    const csv = await new Promise((ok) => {
      const fr = new FileReader()
      fr.onload = () => ok(fr.result)
      fr.readAsText(blobs[0])
    })
    expect(csv).toBe('Comment,Designator,Footprint,JLCPCB Part #\nEXT,"R1,R2",0603,C77\nGHOST,U1,,\n')
    await new Promise((r) => setTimeout(r, 0))
  } finally {
    [URL.createObjectURL, URL.revokeObjectURL] = saved
  }
})

test('a list with no designators offers no JLCPCB file', async () => {
  mockParts()
  renderPage()
  check('NE555P 5')
  await waitFor(() => expect(screen.getByText(/1 of 1 lines can be ordered/i)).toBeInTheDocument())
  expect(screen.queryByRole('button', { name: /download jlcpcb bom/i })).toBeNull()
  expect(screen.queryByText(/for the jlcpcb bom/i)).toBeNull()
})
