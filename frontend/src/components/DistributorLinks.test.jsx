import { render, screen } from '@testing-library/react'
import { test, expect } from 'vitest'
import DistributorLinks from './DistributorLinks.jsx'

test('renders LCSC and JLCPCB search-by-code links with safe rel/target', () => {
  render(<DistributorLinks code="C25804" />)

  const lcsc = screen.getByRole('link', { name: /View on LCSC/i })
  expect(lcsc).toHaveAttribute('href', 'https://www.lcsc.com/search?q=C25804')
  expect(lcsc).toHaveAttribute('target', '_blank')
  expect(lcsc).toHaveAttribute('rel', 'noopener noreferrer')

  const jlc = screen.getByRole('link', { name: /View on JLCPCB/i })
  expect(jlc).toHaveAttribute('href', 'https://jlcpcb.com/parts/componentSearch?searchTxt=C25804')
  expect(jlc).toHaveAttribute('target', '_blank')
  expect(jlc).toHaveAttribute('rel', 'noopener noreferrer')
})
