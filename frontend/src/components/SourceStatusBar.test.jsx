import { render, screen } from '@testing-library/react'
import { test, expect } from 'vitest'
import SourceStatusBar from './SourceStatusBar.jsx'

const ok = (d) => ({ distributor: d, state: 'ok', detail: null, as_of: null })

test('renders nothing when every source answered', () => {
  const { container } = render(<SourceStatusBar sources={[ok('lcsc'), ok('mouser')]} />)
  expect(container).toBeEmptyDOMElement()
})

test('renders nothing when the only non-ok sources are disabled', () => {
  const { container } = render(<SourceStatusBar sources={[
    ok('lcsc'),
    { distributor: 'mouser', state: 'disabled', detail: 'no api key', as_of: null },
  ]} />)
  expect(container).toBeEmptyDOMElement()
})

test('renders nothing when sources is missing', () => {
  const { container } = render(<SourceStatusBar sources={undefined} />)
  expect(container).toBeEmptyDOMElement()
})

test('names each degraded source with readable copy', () => {
  render(<SourceStatusBar sources={[
    ok('lcsc'),
    { distributor: 'mouser', state: 'timeout', detail: 'read timeout', as_of: null },
    { distributor: 'digikey', state: 'quota_exhausted', detail: null, as_of: null },
  ]} />)
  expect(screen.getByText(/Showing partial results/i)).toBeInTheDocument()
  expect(screen.getByText(/Mouser timed out/)).toBeInTheDocument()
  expect(screen.getByText(/DigiKey daily quota used up/)).toBeInTheDocument()
})

test('is announced to assistive tech as a status', () => {
  render(<SourceStatusBar sources={[
    { distributor: 'mouser', state: 'unavailable', detail: null, as_of: null },
  ]} />)
  expect(screen.getByRole('status')).toBeInTheDocument()
})

test('falls back to the raw state rather than rendering nothing for it', () => {
  render(<SourceStatusBar sources={[
    { distributor: 'mouser', state: 'something_new', detail: null, as_of: null },
  ]} />)
  expect(screen.getByText(/Mouser something_new/)).toBeInTheDocument()
})
