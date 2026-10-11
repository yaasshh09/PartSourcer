import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom'
import { vi, beforeEach, afterEach, test, expect } from 'vitest'
import ComparePage from './ComparePage.jsx'
import { CompareProvider } from '../compare.jsx'
import * as api from '../api.js'

function offer(over = {}) {
  return { distributor: 'lcsc', sku: 'C1', mpn_as_listed: 'X', match_tier: 'exact', match_note: null,
    stock: 100, in_stock: true, price_usd: 0.5, price_breaks: null, currency: 'USD',
    product_url: null, as_of: '2026-09-27T08:00:00Z', is_basic: null, is_preferred: null, ...over }
}

function part(key, over = {}, offerOver = {}) {
  return { mpn_key: key, mpn: key, brand: null, package: '0603', description: '',
    datasheet_url: null, offers: [offer(offerOver)], cheapest: null,
    cheapest_unavailable_reason: null, as_of: '2026-09-27T08:00:00Z', ...over }
}

const PARTS = {
  A: part('A', {}, { price_usd: 0.5, stock: 10 }),
  B: part('B', { brand: 'Yageo' }, { price_usd: 0.2, stock: 5000, distributor: 'mouser' }),
  C: part('C', {}, { price_usd: null, stock: 3 }),
}

let where
function Where() { where = useLocation(); return null }

function renderAt(path) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <CompareProvider>
        <Routes><Route path="/compare" element={<><ComparePage /><Where /></>} /></Routes>
      </CompareProvider>
    </MemoryRouter>)
}

beforeEach(() => {
  localStorage.clear()
  vi.restoreAllMocks()
  vi.spyOn(api, 'getPart').mockImplementation((k) =>
    (PARTS[k] ? Promise.resolve({ part: PARTS[k], sources: [] }) : Promise.reject(new api.ApiError(404, 'Part not found'))))
})
afterEach(() => { vi.restoreAllMocks(); localStorage.clear() })

test('one column per part in the URL, each linking to its page', async () => {
  renderAt('/compare?k=A&k=B')
  expect(await screen.findByRole('link', { name: 'B' })).toHaveAttribute('href', '/part/B')
  expect(screen.getByRole('link', { name: 'A' })).toHaveAttribute('href', '/part/A')
  expect(api.getPart).toHaveBeenCalledTimes(2)
})

test('marks the lowest price and the most stock as facts about these parts', async () => {
  renderAt('/compare?k=A&k=B&k=C')
  await screen.findByRole('link', { name: 'C' })
  await waitFor(() => expect(screen.getAllByText('lowest price here')).toHaveLength(1))
  const price = screen.getByText('lowest price here').closest('td')
  expect(price).toHaveTextContent('$0.2')
  expect(price).toHaveTextContent('Mouser')
  expect(screen.getByText('most stock here').closest('td')).toHaveTextContent('5,000')
})

test('says these are not equivalents and never says cheapest or live', async () => {
  const { container } = renderAt('/compare?k=A&k=B')
  await screen.findByRole('link', { name: 'B' })
  expect(screen.getByText(/not equivalents/i)).toBeInTheDocument()
  expect(container.textContent).not.toMatch(/cheapest|live/i)
})

test('missing values read not listed', async () => {
  renderAt('/compare?k=A&k=B')
  await screen.findByRole('link', { name: 'B' })
  expect(screen.getAllByText('not listed').length).toBeGreaterThan(0)
})

test('one part failing leaves the others standing', async () => {
  renderAt('/compare?k=A&k=NOPE')
  expect(await screen.findByText(/Part not found/)).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'A' })).toBeInTheDocument()
})

test('the URL replaces whatever was pinned before', async () => {
  localStorage.setItem('ps-compare', JSON.stringify(['X']))
  renderAt('/compare?k=A&k=B')
  await screen.findByRole('link', { name: 'B' })
  await waitFor(() => expect(JSON.parse(localStorage.getItem('ps-compare'))).toEqual(['A', 'B']))
})

test('a bare /compare opens the pinned parts', async () => {
  localStorage.setItem('ps-compare', JSON.stringify(['A', 'B']))
  renderAt('/compare')
  expect(await screen.findByRole('link', { name: 'B' })).toBeInTheDocument()
  expect(where.search).toBe('?k=A&k=B')
})

test('nothing pinned and nothing in the URL explains how to start', () => {
  renderAt('/compare')
  expect(screen.getByText('NOTHING TO COMPARE YET')).toBeInTheDocument()
})

test('more than four keys shows four, in order, without duplicates', async () => {
  renderAt('/compare?k=A&k=A&k=B&k=C&k=NOPE&k=Z')
  await screen.findByRole('link', { name: 'B' })
  expect(api.getPart.mock.calls.map((c) => c[0])).toEqual(['A', 'B', 'C', 'NOPE'])
})

test('removing a column updates the URL and the tray', async () => {
  renderAt('/compare?k=A&k=B')
  await screen.findByRole('link', { name: 'B' })
  fireEvent.click(screen.getByRole('button', { name: 'Remove A' }))
  await waitFor(() => expect(where.search).toBe('?k=B'))
  expect(JSON.parse(localStorage.getItem('ps-compare'))).toEqual(['B'])
})

test('removing the last column lands on the empty state', async () => {
  renderAt('/compare?k=A')
  await screen.findByRole('link', { name: 'A' })
  fireEvent.click(screen.getByRole('button', { name: 'Remove A' }))
  expect(await screen.findByText('NOTHING TO COMPARE YET')).toBeInTheDocument()
})
