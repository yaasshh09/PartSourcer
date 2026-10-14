import { render, screen, waitFor } from '@testing-library/react'
import { vi, beforeEach, test, expect } from 'vitest'
import PriceHistory from './PriceHistory.jsx'
import * as api from '../api.js'

beforeEach(() => { vi.restoreAllMocks() })

const pts = (...rows) => rows.map(([at, price_usd, stock]) => ({ at, price_usd, stock }))

test('draws price and stock lines with the range and where the numbers come from', async () => {
  vi.spyOn(api, 'getHistory').mockResolvedValue({ recording: true, distributor: 'lcsc',
    points: pts(['2026-09-01T03:00:00Z', 0.0021, 12000], ['2026-09-02T03:00:00Z', 0.0019, 9000],
      ['2026-09-03T03:00:00Z', 0.0024, 15000]) })
  render(<PriceHistory mpnKey="RC0402" />)
  await waitFor(() => expect(screen.getByText('PRICE HISTORY')).toBeInTheDocument())
  expect(api.getHistory).toHaveBeenCalledWith('RC0402')
  expect(screen.getByRole('img', { name: /price from \$0\.0019 to \$0\.0024/i })).toBeInTheDocument()
  expect(screen.getByRole('img', { name: /stock from 9,000 to 15,000/i })).toBeInTheDocument()
  expect(screen.getByText(/3 nightly LCSC readings since/i)).toBeInTheDocument()
})

test('stays hidden with fewer than two readings, no recorder, or an error', async () => {
  const cases = [
    () => Promise.resolve({ recording: true, points: pts(['2026-09-01T03:00:00Z', 1, 1]) }),
    () => Promise.resolve({ recording: false, points: [] }),
    () => Promise.reject(new api.ApiError(503, 'down')),
  ]
  for (const c of cases) {
    vi.spyOn(api, 'getHistory').mockImplementation(c)
    const { container, unmount } = render(<PriceHistory mpnKey="X" />)
    await waitFor(() => expect(api.getHistory).toHaveBeenCalled())
    await Promise.resolve()
    expect(container).toBeEmptyDOMElement()
    unmount()
    vi.restoreAllMocks()
  }
})

test('a flat line still draws instead of dividing by zero', async () => {
  vi.spyOn(api, 'getHistory').mockResolvedValue({ recording: true,
    points: pts(['2026-09-01T03:00:00Z', 0.5, 100], ['2026-09-02T03:00:00Z', 0.5, 100]) })
  const { container } = render(<PriceHistory mpnKey="X" />)
  await waitFor(() => expect(screen.getByText('PRICE HISTORY')).toBeInTheDocument())
  for (const line of container.querySelectorAll('polyline')) {
    expect(line.getAttribute('points')).not.toMatch(/NaN/)
  }
  expect(screen.getByRole('img', { name: /price held at \$0\.50/i })).toBeInTheDocument()
})
