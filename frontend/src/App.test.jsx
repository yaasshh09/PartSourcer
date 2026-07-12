import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import App from './App.jsx'

function renderAt(path) {
  return render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>)
}

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
