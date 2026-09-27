import { render, screen, fireEvent } from '@testing-library/react'
import { beforeEach, test, expect } from 'vitest'
import PinButton from './PinButton.jsx'
import { CompareProvider } from '../compare.jsx'

beforeEach(() => { localStorage.clear() })

const inTray = (ui) => render(<CompareProvider>{ui}</CompareProvider>)

test('renders nothing outside a provider', () => {
  const { container } = render(<PinButton mpnKey="A" />)
  expect(container).toBeEmptyDOMElement()
})

test('toggles a part in and out', () => {
  inTray(<PinButton mpnKey="A" />)
  fireEvent.click(screen.getByRole('button', { name: '+ Compare' }))
  expect(screen.getByRole('button', { name: '✓ Comparing' })).toHaveAttribute('aria-pressed', 'true')
  fireEvent.click(screen.getByRole('button', { name: '✓ Comparing' }))
  expect(screen.getByRole('button', { name: '+ Compare' })).toHaveAttribute('aria-pressed', 'false')
})

test('says the tray is full instead of silently doing nothing', () => {
  localStorage.setItem('ps-compare', JSON.stringify(['A', 'B', 'C', 'D']))
  inTray(<><PinButton mpnKey="E" /><PinButton mpnKey="A" /></>)
  expect(screen.getByRole('button', { name: 'Tray full (4)' })).toBeDisabled()
  // A part already pinned can still be taken out when the tray is full.
  expect(screen.getByRole('button', { name: '✓ Comparing' })).toBeEnabled()
})
