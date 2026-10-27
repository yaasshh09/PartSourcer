import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import Landing from './Landing.jsx'

const wrap = () => render(<MemoryRouter><Landing /></MemoryRouter>)

test('keeps the pitch the search page has always opened with', () => {
  wrap()

  expect(screen.getByText('WHY PARTSOURCER')).toBeInTheDocument()
})

// The rules and the audience live on About. Spelled out here too, the same
// copy sat twice a click apart, so the landing points there instead.
test('points to the rules on About instead of repeating them', () => {
  const { container } = wrap()

  const link = screen.getByRole('link', { name: /four rules/i })
  expect(link.getAttribute('href')).toBe('/about')
  expect(container.textContent).not.toMatch(/never invent a price/i)
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

test('leaves who it is for to the About page', () => {
  const { container } = wrap()

  expect(container.textContent).not.toMatch(/who it.s for/i)
})

test('lists the future plans that were already promised', () => {
  const { container } = wrap()

  expect(container.textContent).toMatch(/future plans/i)
  expect(container.textContent).toMatch(/savings/i)
})

// Part pages chart price history now, so it is no longer a plan.
test('no longer lists price history as a future plan', () => {
  wrap()

  expect(screen.queryByText('Price history')).toBeNull()
})

test('points spec-first visitors at browse', () => {
  wrap()

  expect(screen.getByRole('link', { name: /browse by category/i }))
    .toHaveAttribute('href', '/browse')
})

// Browse shipped, so listing it under future plans would describe a live
// feature as unbuilt.
test('no longer lists browse as a future plan', () => {
  wrap()

  expect(screen.queryByText('Browse by category')).toBeNull()
})

// The BOM check shipped too, and the landing points at it instead.
test('sends a whole parts list to the BOM check, not to future plans', () => {
  wrap()

  expect(screen.queryByText('BOM bulk upload')).toBeNull()
  expect(screen.getByRole('link', { name: /bom check/i })).toHaveAttribute('href', '/bom')
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
