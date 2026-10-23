import { render, screen, fireEvent, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { vi, beforeEach, test, expect } from 'vitest'
import WatchlistPage from './WatchlistPage.jsx'
import WatchButton from '../components/WatchButton.jsx'
import { saveWatch, snapshot, loadWatch } from '../watch.js'
import * as api from '../api.js'

const offer = (over = {}) => ({ distributor: 'lcsc', sku: 'C1', price_usd: 0.01, stock: 5000,
  in_stock: true, currency: 'USD', match_tier: 'exact', as_of: '2026-10-01T00:00:00Z', ...over })
const part = (key, offers) => ({ mpn_key: key, mpn: key, offers, cheapest: null, as_of: '2026-10-01T00:00:00Z' })

const at = (ui) => render(<MemoryRouter>{ui}</MemoryRouter>)

beforeEach(() => {
  localStorage.clear()
  vi.restoreAllMocks()
})

test('the button watches and unwatches a part', () => {
  at(<WatchButton part={part('R1', [offer()])} />)
  fireEvent.click(screen.getByRole('button', { name: '☆ Watch' }))
  expect(screen.getByRole('button', { name: '★ Watching' })).toHaveAttribute('aria-pressed', 'true')
  expect(loadWatch().map((e) => e.k)).toEqual(['R1'])
  expect(screen.getByRole('link', { name: 'Watchlist' })).toHaveAttribute('href', '/watchlist')
  fireEvent.click(screen.getByRole('button', { name: '★ Watching' }))
  expect(loadWatch()).toEqual([])
})

test('an empty watchlist says how to add to it', () => {
  at(<WatchlistPage />)
  expect(screen.getByText(/NOTHING WATCHED YET/)).toBeInTheDocument()
})

test('each part shows what it was when watched and what that listing says now', async () => {
  saveWatch([
    snapshot(part('UP', [offer()]), '2026-10-02T00:00:00Z'),
    snapshot(part('GONE', [offer({ sku: 'C9' })]), '2026-10-02T00:00:00Z'),
    snapshot(part('BAD', [offer()]), '2026-10-02T00:00:00Z'),
  ])
  vi.spyOn(api, 'getPart').mockImplementation((k) => {
    if (k === 'UP') return Promise.resolve({ part: part('UP', [offer({ price_usd: 0.012, stock: 3000 })]) })
    if (k === 'GONE') return Promise.resolve({ part: part('GONE', [offer({ distributor: 'mouser', sku: 'M1' })]) })
    return Promise.reject(Object.assign(new Error('x'), { detail: 'Upstream timed out' }))
  })
  at(<WatchlistPage />)

  const up = await screen.findByRole('listitem', { name: 'UP' })
  expect(await within(up).findByText(/\$0\.0120/)).toBeInTheDocument()
  expect(within(up).getByText(/up \$0\.0020/)).toBeInTheDocument()
  expect(within(up).getByText(/2,000 fewer/)).toBeInTheDocument()

  const gone = screen.getByRole('listitem', { name: 'GONE' })
  expect(await within(gone).findByText(/No longer listed at LCSC/)).toBeInTheDocument()

  const bad = screen.getByRole('listitem', { name: 'BAD' })
  expect(await within(bad).findByText(/Upstream timed out/)).toBeInTheDocument()
})

test('removing a part takes it off the page and out of storage', async () => {
  saveWatch([snapshot(part('A', [offer()])), snapshot(part('B', [offer()]))])
  vi.spyOn(api, 'getPart').mockImplementation((k) => Promise.resolve({ part: part(k, [offer()]) }))
  at(<WatchlistPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Stop watching A' }))
  expect(screen.queryByRole('listitem', { name: 'A' })).toBeNull()
  expect(loadWatch().map((e) => e.k)).toEqual(['B'])
})
