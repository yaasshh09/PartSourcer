import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import Footer from './Footer.jsx'
import { CONTACT } from '../contact.js'

const wrap = () => render(<MemoryRouter><Footer /></MemoryRouter>)

test('links the repo', () => {
  wrap()

  expect(screen.getByRole('link', { name: /github/i }))
    .toHaveAttribute('href', CONTACT.repoUrl)
})

// It used to be plain grey text, which reads as a label rather than something
// you can go and check. The licence is a claim, so it should be verifiable.
test('the MIT licence goes to the actual licence file', () => {
  wrap()

  expect(screen.getByRole('link', { name: /MIT/i }))
    .toHaveAttribute('href', CONTACT.licenseUrl)
})

test('shows the current year, read at render rather than hardcoded', () => {
  wrap()

  const year = String(new Date().getFullYear())
  expect(screen.getByText(new RegExp(`© ${year} PartSourcer`))).toBeInTheDocument()
})

test('does not ship the 404 demo link', () => {
  wrap()

  // The 404 page is reachable by mistyping any URL. Advertising it beside
  // GitHub and the licence read as a dev artifact left switched on.
  expect(screen.queryByRole('link', { name: /404/i })).not.toBeInTheDocument()
})

test('carries the contact routes people actually use', () => {
  wrap()

  expect(screen.getByRole('link', { name: new RegExp(CONTACT.email, 'i') }))
    .toHaveAttribute('href', `mailto:${CONTACT.email}`)
  expect(screen.getByRole('link', { name: /instagram/i }))
    .toHaveAttribute('href', CONTACT.instagramUrl)
})

// Mouser and DigiKey are queried now, so disclaiming LCSC alone understates
// who we are unaffiliated with.
test('disclaims every distributor it queries, not just LCSC', () => {
  const { container } = wrap()

  const text = container.textContent
  expect(text).toMatch(/not affiliated with or endorsed by/i)
  for (const name of ['LCSC', 'JLCPCB', 'Mouser', 'DigiKey']) {
    expect(text).toContain(name)
  }
})

test('offers a route to every page the nav does', () => {
  wrap()

  for (const label of ['Search', 'About', 'How it works', 'FAQ', 'Contact']) {
    expect(screen.getByRole('link', { name: label })).toBeInTheDocument()
  }
})

test('every outbound link is safe to open in a new tab', () => {
  const { container } = wrap()

  for (const a of container.querySelectorAll('a[target="_blank"]')) {
    expect(a).toHaveAttribute('rel', expect.stringContaining('noreferrer'))
  }
})
