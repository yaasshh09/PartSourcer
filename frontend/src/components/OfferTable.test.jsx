import { render, screen, fireEvent } from '@testing-library/react'
import { test, expect, afterEach } from 'vitest'
import OfferTable from './OfferTable.jsx'

const origClipboard = Object.getOwnPropertyDescriptor(navigator, 'clipboard')
afterEach(() => {
  if (origClipboard) Object.defineProperty(navigator, 'clipboard', origClipboard)
  else delete navigator.clipboard
})
function noClipboard() {
  Object.defineProperty(navigator, 'clipboard', { value: undefined, configurable: true })
}
function withClipboard() {
  Object.defineProperty(navigator, 'clipboard', {
    value: { writeText: () => Promise.resolve() }, configurable: true,
  })
}

function offer(over = {}) {
  return {
    distributor: 'lcsc', sku: 'C25531', mpn_as_listed: 'NE555P',
    match_tier: 'exact', match_note: null, stock: 9360, in_stock: true,
    price_usd: 0.5, price_breaks: null, currency: 'USD', product_url: null,
    as_of: '2026-08-15T07:52:24Z', is_basic: true, is_preferred: false,
    ...over,
  }
}

test('renders one row per offer under an exact-match heading', () => {
  noClipboard()
  render(<OfferTable offers={[offer(), offer({ distributor: 'mouser', sku: 'M-1', price_usd: 0.6 })]} />)
  expect(screen.getByText(/EXACT MATCH/i)).toBeInTheDocument()
  expect(screen.getByText('LCSC')).toBeInTheDocument()
  expect(screen.getByText('Mouser')).toBeInTheDocument()
  expect(screen.getByText('C25531')).toBeInTheDocument()
  expect(screen.getByText('$0.50')).toBeInTheDocument()
})

test('an offer with no price says so instead of leaving the cell blank', () => {
  noClipboard()
  render(<OfferTable offers={[offer({ price_usd: null })]} />)
  expect(screen.getByText('no price')).toBeInTheDocument()
  expect(screen.queryByText('$0.0000')).not.toBeInTheDocument()
})

test('an offer with no SKU says so, and offers nothing to copy', () => {
  // The clipboard is available here on purpose: the copy button must be
  // missing because there is no code to copy, not because of the environment.
  withClipboard()
  render(<OfferTable offers={[offer({ sku: '' })]} />)
  expect(screen.getByText('no SKU')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /^Copy/ })).not.toBeInTheDocument()
})

test('column headers are scoped, which is the reason for a real table', () => {
  noClipboard()
  render(<OfferTable offers={[offer()]} />)
  const headers = screen.getAllByRole('columnheader')
  expect(headers).toHaveLength(6)
  headers.forEach((h) => expect(h).toHaveAttribute('scope', 'col'))
})

test('the table scrolls in its own box so the page never scrolls sideways', () => {
  noClipboard()
  const { container } = render(<OfferTable offers={[offer()]} />)
  const table = container.querySelector('table')
  expect(table.parentElement).toHaveStyle({ overflowX: 'auto' })
})

test('omits the packaging block entirely when there are no variants', () => {
  noClipboard()
  render(<OfferTable offers={[offer()]} />)
  expect(screen.queryByText('DIFFERENT PACKAGING')).not.toBeInTheDocument()
})

test('shows packaging variants in their own block with the match note', () => {
  noClipboard()
  render(<OfferTable offers={[
    offer(),
    offer({ sku: 'C99', match_tier: 'packaging', match_note: 'tape and reel (T&R)' }),
  ]} />)
  expect(screen.getByText('DIFFERENT PACKAGING')).toBeInTheDocument()
  expect(screen.getByText(/tape and reel \(T&R\)/)).toBeInTheDocument()
  expect(screen.getByText(/not the same physical part/i)).toBeInTheDocument()
})

test('links only the rows that carry a product_url', () => {
  noClipboard()
  render(<OfferTable offers={[
    offer({ distributor: 'lcsc', sku: 'C1', product_url: null }),
    offer({ distributor: 'mouser', sku: 'M1', product_url: 'https://mouser.com/p/M1' }),
  ]} />)
  const links = screen.getAllByRole('link')
  expect(links).toHaveLength(1)
  expect(links[0]).toHaveAttribute('href', 'https://mouser.com/p/M1')
})

test('names the row the backend called cheapest', () => {
  noClipboard()
  render(<OfferTable
    offers={[offer({ sku: 'C1', price_usd: 0.5 }), offer({ distributor: 'mouser', sku: 'M1', price_usd: 0.4 })]}
    cheapest={{ distributor: 'mouser', sku: 'M1', price_usd: 0.4, compared_sources: 2, of_sources: 2 }} />)
  expect(screen.getByText(/cheapest of 2 sources checked/i)).toBeInTheDocument()
})

test('explains an absent cheapest claim instead of implying one', () => {
  noClipboard()
  render(<OfferTable offers={[offer()]} cheapest={null}
    unavailableReason="compared 1 of 1 sources, need at least 2 to name a cheapest" />)
  expect(screen.getByText(/No cheapest claim: compared 1 of 1 sources/i)).toBeInTheDocument()
  expect(screen.queryByText(/cheapest of/i)).not.toBeInTheDocument()
})

test('renders nothing when there are no offers at all', () => {
  noClipboard()
  const { container } = render(<OfferTable offers={[]} />)
  expect(container).toBeEmptyDOMElement()
})

test('shows a per-row as_of, because distributors cache on different clocks', () => {
  noClipboard()
  render(<OfferTable offers={[
    offer({ sku: 'C1', as_of: '2026-08-15T07:52:24Z' }),
    offer({ distributor: 'mouser', sku: 'M1', as_of: '2026-08-14T03:10:00Z' }),
  ]} />)
  expect(screen.getByText(/Aug 15, 2026/)).toBeInTheDocument()
  expect(screen.getByText(/Aug 14, 2026/)).toBeInTheDocument()
})

// The real cost of an order includes shipping and tax, which no distributor
// API quotes. Say so next to the prices rather than let them read as final.
test('says the prices leave out shipping and tax', () => {
  render(<OfferTable offers={[offer()]} />)
  expect(screen.getByText(/shipping, tax and import duties/i)).toBeInTheDocument()
})

// Mouser and DigiKey publish a ladder. Showing only the single-unit price
// hides what a builder ordering a hundred would actually pay.
test('lists the quantity price breaks a distributor published', () => {
  noClipboard()
  const breaks = [{ qty: 100, price_usd: 0.014 }, { qty: 1, price_usd: 0.5 }, { qty: 10, price_usd: 0.3 }]
  render(<OfferTable offers={[offer({ distributor: 'mouser', sku: 'M-1', price_breaks: breaks })]} />)
  expect(screen.getByText('3 price breaks')).toBeInTheDocument()
  expect(screen.getByText('100+')).toBeInTheDocument()
  expect(screen.getByText('$0.0140')).toBeInTheDocument()
  const qtys = screen.getAllByText(/^\d+\+$/).map((n) => n.textContent)
  expect(qtys).toEqual(['1+', '10+', '100+'])
})

test('no ladder line when there is nothing beyond the unit price', () => {
  noClipboard()
  render(<OfferTable offers={[offer(), offer({ distributor: 'mouser', sku: 'M-1',
    price_breaks: [{ qty: 1, price_usd: 0.5 }] })]} />)
  expect(screen.queryByText(/price breaks/)).not.toBeInTheDocument()
})

// Same rules as the BOM check, so a quantity costs the same on both pages.
test('prices every offer at the quantity typed in', () => {
  noClipboard()
  const ladder = [{ qty: 1, price_usd: 0.5 }, { qty: 10, price_usd: 0.3 }, { qty: 100, price_usd: 0.1 }]
  render(<OfferTable offers={[
    offer({ distributor: 'mouser', sku: 'M-1', stock: 5000, price_breaks: ladder }),
    offer({ distributor: 'digikey', sku: 'D-1', stock: 5000, price_breaks: [{ qty: 500, price_usd: 0.02 }] }),
    offer({ sku: 'C1', stock: 100, price_usd: 0.05 }),
  ]} />)
  fireEvent.change(screen.getByLabelText(/price for how many/i), { target: { value: '250' } })
  expect(screen.getByText('250 for $25.00')).toBeInTheDocument()
  expect(screen.getByText('500 for $10.00')).toBeInTheDocument()
  expect(screen.getByText('minimum order 500')).toBeInTheDocument()
  expect(screen.getByText('250 for $12.50')).toBeInTheDocument()
  expect(screen.getByText('only 100 in stock')).toBeInTheDocument()
})

test('shows no quantity line until a quantity is typed', () => {
  noClipboard()
  render(<OfferTable offers={[offer()]} />)
  expect(screen.queryByText(/ for \$/)).not.toBeInTheDocument()
  fireEvent.change(screen.getByLabelText(/price for how many/i), { target: { value: '0' } })
  expect(screen.queryByText(/ for \$/)).not.toBeInTheDocument()
})
