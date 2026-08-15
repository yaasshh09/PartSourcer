import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { vi, afterEach } from 'vitest'
import App from './App.jsx'
import * as api from './api.js'

function renderAt(path) {
  return render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>)
}

afterEach(() => { vi.restoreAllMocks() })

test('nav + footer present on home', () => {
  renderAt('/')
  expect(screen.getAllByText('PARTSOURCER').length).toBeGreaterThan(0)
  expect(screen.getByText(/Not affiliated/)).toBeInTheDocument()
})

test('unknown route shows 404 page', () => {
  renderAt('/nope')
  expect(screen.getByText('404')).toBeInTheDocument()
})

test('about route resolves', () => {
  renderAt('/about')
  expect(screen.getByText('ABOUT')).toBeInTheDocument()
})

// Pins the splat route in App.jsx. DetailPage.test.jsx declares its own
// /part/* route, so without this the app route could be reverted to a named
// param and the whole suite would stay green while every real detail page
// fetched an empty key. The keys stay pending so the page holds its loading
// state: a named param would not match a slash and would fall to NotFoundPage.
test('a slash-bearing MPN reaches the detail page, not the 404 page', () => {
  vi.spyOn(api, 'getPart').mockReturnValue(new Promise(() => {}))
  vi.spyOn(api, 'getEquivalent').mockReturnValue(new Promise(() => {}))
  renderAt('/part/LM358P/NOPB')
  expect(screen.getByText('Loading…')).toBeInTheDocument()
  expect(screen.queryByText('404')).not.toBeInTheDocument()
})
