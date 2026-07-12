import { render, screen } from '@testing-library/react'
import App from './App.jsx'

test('app renders', () => {
  render(<App />)
  expect(screen.getByText('PartSourcer')).toBeInTheDocument()
})
