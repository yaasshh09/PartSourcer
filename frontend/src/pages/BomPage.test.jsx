import { render, screen, waitFor, fireEvent } from '@testing-library/react'
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
}

function mockParts(failing = {}) {
  return vi.spyOn(api, 'getPart').mockImplementation((k) => {
    if (failing[k]) return Promise.reject(failing[k])
    if (PARTS[k]) return Promise.resolve({ part: PARTS[k], sources: [] })
    return Promise.reject(new api.ApiError(404, `Part ${k} not found`))
  })
}

const renderPage = () => render(<MemoryRouter><BomPage /></MemoryRouter>)

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
