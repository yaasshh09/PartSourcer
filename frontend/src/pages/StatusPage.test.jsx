import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { vi, beforeEach, test, expect } from 'vitest'
import StatusPage from './StatusPage.jsx'
import * as api from '../api.js'

beforeEach(() => { vi.restoreAllMocks() })

const at = () => render(<MemoryRouter><StatusPage /></MemoryRouter>)

test('one row per distributor with what real requests met', async () => {
  vi.spyOn(api, 'getStatus').mockResolvedValue({ window_hours: 24, reads: 42, since: '2026-10-23T00:00:00Z',
    distributors: [
      { distributor: 'lcsc', ok: 40, problems: { timeout: 2 }, last_ok_at: '2026-10-24T01:00:00Z',
        last_problem: { state: 'timeout', at: '2026-10-23T20:00:00Z' }, configured: true },
      { distributor: 'mouser', ok: 0, problems: {}, last_ok_at: null, last_problem: null, configured: false },
      { distributor: 'digikey', ok: 0, problems: {}, last_ok_at: null, last_problem: null, configured: null },
    ] })
  at()
  expect(await screen.findByText(/42 reads in the past 24 hours/)).toBeInTheDocument()
  const lcsc = screen.getByRole('row', { name: /LCSC/ })
  expect(within(lcsc).getByText('95%')).toBeInTheDocument()
  expect(within(lcsc).getByText('2 timed out')).toBeInTheDocument()
  expect(within(screen.getByRole('row', { name: /Mouser/ })).getByText('not set up on this site')).toBeInTheDocument()
  expect(within(screen.getByRole('row', { name: /DigiKey/ })).getByText('no requests yet')).toBeInTheDocument()
})

test('says so when status cannot be read', async () => {
  vi.spyOn(api, 'getStatus').mockRejectedValue(Object.assign(new Error('x'), { detail: 'Status is unavailable right now' }))
  at()
  expect(await screen.findByText(/Status is unavailable right now/)).toBeInTheDocument()
})
