import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import Nav from './Nav.jsx'

const wrap = () => render(<MemoryRouter><Nav /></MemoryRouter>)

test('carries the pages a reader can go to', () => {
  wrap()

  for (const label of ['Search', 'About', 'How it works', 'FAQ', 'Contact']) {
    expect(screen.getByRole('link', { name: label })).toBeInTheDocument()
  }
})

// The repo is still linked from the footer. The header is for moving around
// the site, and an outbound link there is the one item that takes you off it.
test('does not send you off to GitHub from the header', () => {
  const { container } = wrap()

  expect(container.querySelector('a[href*="github.com"]')).toBeNull()
})
