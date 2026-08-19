import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import Landing from './Landing.jsx'

const wrap = () => render(<MemoryRouter><Landing /></MemoryRouter>)

test('keeps the pitch the search page has always opened with', () => {
  wrap()

  expect(screen.getByText('WHY PARTSOURCER')).toBeInTheDocument()
})

test('walks through the honesty rules, not just the headline one', () => {
  const { container } = wrap()

  for (const rule of [/never fake/i, /never invent a price/i, /fetched differently|measured differently/i]) {
    expect(container.textContent).toMatch(rule)
  }
})

// The worked example carries figures that are not being re-read on page load.
// Unlabelled, that is exactly the frozen price the project promises never to
// show, so the label is the thing that makes the section allowed to exist.
test('marks the worked example as an illustration rather than a reading', () => {
  const { container } = wrap()

  expect(screen.getByTestId('worked-example')).toBeInTheDocument()
  expect(container.textContent).toMatch(/example|illustration/i)
  expect(container.textContent).toMatch(/not live|not a live|illustration/i)
})

test('says who it is for', () => {
  const { container } = wrap()

  expect(container.textContent).toMatch(/who it.s for/i)
})

test('lists the future plans that were already promised', () => {
  const { container } = wrap()

  expect(container.textContent).toMatch(/future plans/i)
  for (const plan of [/BOM/i, /price history/i, /categor/i, /savings/i]) {
    expect(container.textContent).toMatch(plan)
  }
})

test('no longer calls that list coming soon', () => {
  const { container } = wrap()

  expect(container.textContent).not.toMatch(/coming soon/i)
})

test('offers a way to get in touch', () => {
  wrap()

  expect(screen.getByRole('link', { name: /contact|get in touch/i }))
    .toHaveAttribute('href', '/contact')
})

// Same guard the static pages carry. The landing page is the most marketing
// shaped surface here, so it is the most likely to drift.
test('claims nothing the matcher cannot back up', () => {
  const { container } = wrap()

  for (const claim of [/similar part/i, /live stock/i, /pin.?compatib/i]) {
    expect(container.textContent).not.toMatch(claim)
  }
})
