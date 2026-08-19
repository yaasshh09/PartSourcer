import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { test, expect, afterEach, vi } from 'vitest'
import ResultCard from './ResultCard.jsx'

function offer(over = {}) {
  return {
    distributor: 'lcsc', sku: 'C8734', mpn_as_listed: 'STM32F103C8T6',
    match_tier: 'exact', match_note: null, stock: 214596, in_stock: true,
    price_usd: 1.0371, price_breaks: null, currency: 'USD', product_url: null,
    as_of: '2026-08-15T07:52:24Z', is_basic: null, is_preferred: null,
    ...over,
  }
}

function part(over = {}) {
  return {
    mpn_key: 'STM32F103C8T6', mpn: 'STM32F103C8T6', brand: null,
    package: 'LQFP-48(7x7)', description: 'ARM MCU', datasheet_url: null,
    offers: [offer()], cheapest: null,
    cheapest_unavailable_reason: 'compared 1 of 1 sources, need at least 2 to name a cheapest',
    as_of: '2026-08-15T07:52:24Z',
    ...over,
  }
}

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

function renderCard(p) {
  return render(<MemoryRouter><ResultCard part={p} /></MemoryRouter>)
}

test('shows mpn, package, headline price and stock, and links by mpn_key', () => {
  setClipboard(null)
  renderCard(part())
  expect(screen.getByText('STM32F103C8T6')).toBeInTheDocument()
  expect(screen.getByText('LQFP-48(7x7)')).toBeInTheDocument()
  expect(screen.getByText('$1.04')).toBeInTheDocument()
  expect(screen.getByText('214,596 IN STOCK')).toBeInTheDocument()
  const links = screen.getAllByRole('link')
  expect(links.length).toBeGreaterThan(0)
  links.forEach((l) => expect(l).toHaveAttribute('href', '/part/STM32F103C8T6'))
})

test('a part whose only offer has no price says so instead of showing nothing', () => {
  setClipboard(null)
  renderCard(part({ offers: [offer({ price_usd: null })] }))
  expect(screen.getByText('no price')).toBeInTheDocument()
})

test('escapes a key that would break the URL, but keeps the slash', () => {
  setClipboard(null)
  renderCard(part({ mpn_key: 'LM358P/NOPB', mpn: 'LM358P/NOPB' }))
  screen.getAllByRole('link').forEach((l) =>
    expect(l).toHaveAttribute('href', '/part/LM358P/NOPB'))
})

test('copies the MPN, and the copy button is not nested inside a link', () => {
  setClipboard(vi.fn().mockResolvedValue())
  renderCard(part())
  const btn = screen.getByRole('button', { name: /Copy STM32F103C8T6/i })
  expect(btn).toBeInTheDocument()
  expect(btn.closest('a')).toBeNull()
})

test('description subtitle shown when present', () => {
  setClipboard(null)
  renderCard(part())
  expect(screen.getByText('ARM MCU')).toBeInTheDocument()
})

test('empty description subtitle is omitted', () => {
  setClipboard(null)
  renderCard(part({ description: '' }))
  expect(screen.queryByText('ARM MCU')).not.toBeInTheDocument()
})

test('claims cheapest only when the backend made the claim', () => {
  setClipboard(null)
  renderCard(part())
  expect(screen.queryByText(/cheapest of/i)).not.toBeInTheDocument()
})

test('shows the cheapest badge with the compared count when the backend claims one', () => {
  setClipboard(null)
  renderCard(part({
    offers: [offer(), offer({ distributor: 'mouser', sku: 'M-1', price_usd: 0.9 })],
    cheapest: { distributor: 'mouser', sku: 'M-1', price_usd: 0.9, compared_sources: 2, of_sources: 3 },
    cheapest_unavailable_reason: null,
  }))
  expect(screen.getByText(/cheapest of 2 sources checked/i)).toBeInTheDocument()
  expect(screen.getByText('$0.90')).toBeInTheDocument()
})

test('shows no offer count for a single offer', () => {
  setClipboard(null)
  renderCard(part())
  expect(screen.queryByText(/offers/i)).not.toBeInTheDocument()
})

test('shows an offer count when there is more than one offer', () => {
  setClipboard(null)
  renderCard(part({ offers: [offer(), offer({ distributor: 'mouser', sku: 'M-1' })] }))
  expect(screen.getByText('2 offers')).toBeInTheDocument()
})

test('shows Basic only when the LCSC offer actually carries the flag', () => {
  setClipboard(null)
  renderCard(part({ offers: [offer({ is_basic: true, is_preferred: false })] }))
  expect(screen.getByText('Basic')).toBeInTheDocument()
})

test('shows Preferred ahead of Basic when both are set', () => {
  setClipboard(null)
  renderCard(part({ offers: [offer({ is_basic: true, is_preferred: true })] }))
  expect(screen.getByText('Preferred')).toBeInTheDocument()
  expect(screen.queryByText('Basic')).not.toBeInTheDocument()
})

test('invents no flag for a part with no LCSC offer', () => {
  setClipboard(null)
  renderCard(part({ offers: [offer({ distributor: 'mouser', sku: 'M-1' })] }))
  expect(screen.queryByText('Basic')).not.toBeInTheDocument()
  expect(screen.queryByText('Preferred')).not.toBeInTheDocument()
  expect(screen.queryByText('Standard')).not.toBeInTheDocument()
})

test('renders no price block for a part with no offers, rather than $0.00', () => {
  setClipboard(null)
  renderCard(part({ offers: [], cheapest: null }))
  expect(screen.getByText('STM32F103C8T6')).toBeInTheDocument()
  expect(screen.queryByText('$0.00')).not.toBeInTheDocument()
  expect(screen.queryByText(/IN STOCK|OUT OF STOCK/)).not.toBeInTheDocument()
  // Dropping the price must not drop what we do know about the part.
  expect(screen.getByText('LQFP-48(7x7)')).toBeInTheDocument()
})

// Brand comes from Mouser only, so it is present on roughly two thirds of a
// Mouser-heavy query and almost none of an LCSC-heavy one. It has to carry
// its own absence rather than leave an empty line behind.
test('shows the manufacturer when upstream gave us one', () => {
  setClipboard(null)
  renderCard(part({ brand: 'Texas Instruments' }))
  expect(screen.getByText('Texas Instruments')).toBeInTheDocument()
})

test('shows no manufacturer line at all when there is none', () => {
  setClipboard(null)
  const { container } = renderCard(part({ brand: null }))
  expect(screen.queryByTestId('brand')).not.toBeInTheDocument()
  expect(container.textContent).not.toMatch(/unknown|n\/a|\u2014/i)
})
