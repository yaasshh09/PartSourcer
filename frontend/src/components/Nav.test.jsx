import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
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

// jsdom does not apply media queries, so the panel is always in the DOM here.
// What these check is the state the stylesheet keys off, not the pixels.
test('starts with the menu shut', () => {
  wrap()

  expect(screen.getByRole('button', { name: /open menu/i }))
    .toHaveAttribute('aria-expanded', 'false')
  expect(document.getElementById('ps-nav-links')).toHaveAttribute('data-open', 'false')
})

test('opens and shuts on the toggle', () => {
  wrap()

  fireEvent.click(screen.getByRole('button', { name: /open menu/i }))
  expect(document.getElementById('ps-nav-links')).toHaveAttribute('data-open', 'true')

  fireEvent.click(screen.getByRole('button', { name: /close menu/i }))
  expect(document.getElementById('ps-nav-links')).toHaveAttribute('data-open', 'false')
})

test('shuts itself when a link inside it changes the route', () => {
  render(
    <MemoryRouter>
      <Nav />
      <Routes><Route path="*" element={null} /></Routes>
    </MemoryRouter>,
  )

  fireEvent.click(screen.getByRole('button', { name: /open menu/i }))
  expect(document.getElementById('ps-nav-links')).toHaveAttribute('data-open', 'true')

  // The header never unmounts on a route change, so without the effect the
  // panel would sit open on top of the page you just asked for.
  fireEvent.click(screen.getByRole('link', { name: 'About' }))
  expect(document.getElementById('ps-nav-links')).toHaveAttribute('data-open', 'false')
})
