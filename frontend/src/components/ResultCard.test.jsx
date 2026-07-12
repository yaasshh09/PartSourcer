import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import ResultCard from './ResultCard.jsx'

const part = {
  lcsc: 'C8734', mpn: 'STM32F103C8T6', brand: null, package: 'LQFP-48(7x7)',
  description: 'ARM MCU', stock: 214596, price_usd: 1.0371, datasheet_url: null,
  as_of: '2026-07-12T07:52:24Z',
}

function renderCard(p) {
  return render(<MemoryRouter><ResultCard part={p} /></MemoryRouter>)
}

test('shows mpn, package, price, stock label, and links to detail', () => {
  renderCard(part)
  expect(screen.getByText('STM32F103C8T6')).toBeInTheDocument()
  expect(screen.getByText('LQFP-48(7x7)')).toBeInTheDocument()
  expect(screen.getByText('$1.04')).toBeInTheDocument()
  expect(screen.getByText('214,596 IN STOCK')).toBeInTheDocument()
  expect(screen.getByRole('link')).toHaveAttribute('href', '/part/C8734')
})

test('description subtitle shown when present', () => {
  renderCard(part)
  expect(screen.getByText('ARM MCU')).toBeInTheDocument()
})

test('empty description subtitle is omitted (no fake brand)', () => {
  renderCard({ ...part, description: '' })
  expect(screen.queryByText('ARM MCU')).not.toBeInTheDocument()
})
