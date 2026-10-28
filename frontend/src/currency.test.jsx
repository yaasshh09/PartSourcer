import { render, screen, fireEvent } from '@testing-library/react'
import { vi, beforeEach, afterEach, test, expect } from 'vitest'
import { CurrencyProvider, CurrencySelect, useCurrency } from './currency.jsx'
import Price from './components/Price.jsx'
import { setShownCurrency } from './theme.js'
import * as api from './api.js'

// Stands in for App, which subscribes so that a change re-renders the tree.
function Shell() {
  useCurrency()
  return <><CurrencySelect /><p data-testid="p"><Price value={1} /></p></>
}
const page = () => render(<CurrencyProvider><Shell /></CurrencyProvider>)

beforeEach(() => { localStorage.clear(); vi.restoreAllMocks() })
afterEach(() => { setShownCurrency('USD', 1) })

test('switching converts every price and says at which dated rate', async () => {
  vi.spyOn(api, 'getFx').mockResolvedValue({ base: 'USD', date: '2026-10-23', rates: { EUR: 0.9, GBP: 0.75, INR: 95 } })
  page()
  expect(screen.getByTestId('p')).toHaveTextContent('$1.00')
  fireEvent.change(screen.getByRole('combobox', { name: 'Currency' }), { target: { value: 'EUR' } })
  expect(await screen.findByText(/ECB rate of Oct 23, 2026/)).toHaveTextContent('Distributors charge in USD.')
  expect(screen.getByTestId('p')).toHaveTextContent('€0.90')
  expect(localStorage.getItem('ps-currency')).toBe('EUR')
  fireEvent.change(screen.getByRole('combobox', { name: 'Currency' }), { target: { value: 'USD' } })
  expect(screen.getByTestId('p')).toHaveTextContent('$1.00')
})

test('a rate that arrives after a newer choice does not override it', async () => {
  let land
  vi.spyOn(api, 'getFx').mockReturnValue(new Promise((ok) => { land = ok }))
  page()
  const pick = screen.getByRole('combobox', { name: 'Currency' })
  fireEvent.change(pick, { target: { value: 'EUR' } })
  fireEvent.change(pick, { target: { value: 'USD' } })
  land({ base: 'USD', date: '2026-10-23', rates: { EUR: 0.9 } })
  await new Promise((r) => setTimeout(r, 0))
  expect(screen.getByTestId('p')).toHaveTextContent('$1.00')
  expect(pick).toHaveValue('USD')
})

test('a remembered choice is restored on load', async () => {
  localStorage.setItem('ps-currency', 'GBP')
  vi.spyOn(api, 'getFx').mockResolvedValue({ base: 'USD', date: '2026-10-23', rates: { GBP: 0.75 } })
  page()
  expect(await screen.findByText('£0.75')).toBeInTheDocument()
})

test('no rates means dollars and a plain reason', async () => {
  vi.spyOn(api, 'getFx').mockRejectedValue(new Error('down'))
  page()
  fireEvent.change(screen.getByRole('combobox', { name: 'Currency' }), { target: { value: 'INR' } })
  expect(await screen.findByText(/Rates are unavailable/)).toBeInTheDocument()
  expect(screen.getByTestId('p')).toHaveTextContent('$1.00')
  expect(screen.getByRole('combobox', { name: 'Currency' })).toHaveValue('USD')
})
