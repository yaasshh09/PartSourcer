import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import AboutPage from './AboutPage.jsx'
import HowPage from './HowPage.jsx'
import FaqPage from './FaqPage.jsx'
import NotFoundPage from './NotFoundPage.jsx'

const wrap = (el) => render(<MemoryRouter>{el}</MemoryRouter>)

test('about', () => { wrap(<AboutPage />); expect(screen.getByText(/FREE TOOL FOR BUILDERS/)).toBeInTheDocument() })
test('how', () => { wrap(<HowPage />); expect(screen.getByText('SEARCH → MATCH → SAVE.')).toBeInTheDocument() })
test('faq', () => { wrap(<FaqPage />); expect(screen.getByText('QUICK ANSWERS.')).toBeInTheDocument() })
test('404', () => { wrap(<NotFoundPage />); expect(screen.getByText('404')).toBeInTheDocument() })

// The marketing copy used to promise things the code does not do: a "similar
// part" tier that v1 never returns, and "live" numbers when the LCSC side is a
// once-a-day snapshot. Both read as honest until you check them against the
// matcher, so they get pinned here rather than left to drift back in.
const OVERCLAIMS = [/similar part/i, /live stock/i, /pin.?compatib/i]

test.each([
  ['how it works', <HowPage />],
  ['faq', <FaqPage />],
  ['about', <AboutPage />],
])('%s claims nothing the matcher cannot back up', (_name, el) => {
  const { container } = wrap(el)

  for (const claim of OVERCLAIMS) {
    expect(container.textContent).not.toMatch(claim)
  }
})

test('the faq names the real freshness limit, not just our cache', () => {
  wrap(<FaqPage />)

  expect(screen.getByText(/syncs about once a day/i)).toBeInTheDocument()
})
