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
