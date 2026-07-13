import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { test, expect, afterEach, vi } from 'vitest'
import ResultCard from './ResultCard.jsx'

const part = {
  lcsc: 'C8734', mpn: 'STM32F103C8T6', brand: null, package: 'LQFP-48(7x7)',
  description: 'ARM MCU', stock: 214596, price_usd: 1.0371, datasheet_url: null,
  as_of: '2026-07-12T07:52:24Z',
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

test('shows mpn, package, price, stock label, and links to detail', () => {
  setClipboard(null)
  renderCard(part)
  expect(screen.getByText('STM32F103C8T6')).toBeInTheDocument()
  expect(screen.getByText('LQFP-48(7x7)')).toBeInTheDocument()
  expect(screen.getByText('$1.04')).toBeInTheDocument()
  expect(screen.getByText('214,596 IN STOCK')).toBeInTheDocument()
  const links = screen.getAllByRole('link')
  expect(links.length).toBeGreaterThan(0)
  links.forEach((l) => expect(l).toHaveAttribute('href', '/part/C8734'))
})

test('copy button is present and is not nested inside a link', () => {
  setClipboard(vi.fn().mockResolvedValue())
  renderCard(part)
  const btn = screen.getByRole('button', { name: /Copy C8734/i })
  expect(btn).toBeInTheDocument()
  expect(btn.closest('a')).toBeNull()
})

test('description subtitle shown when present', () => {
  setClipboard(null)
  renderCard(part)
  expect(screen.getByText('ARM MCU')).toBeInTheDocument()
})

test('empty description subtitle is omitted (no fake brand)', () => {
  setClipboard(null)
  renderCard({ ...part, description: '' })
  expect(screen.queryByText('ARM MCU')).not.toBeInTheDocument()
})
