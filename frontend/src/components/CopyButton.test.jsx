import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { vi, test, expect, afterEach } from 'vitest'
import CopyButton from './CopyButton.jsx'

const origClipboard = Object.getOwnPropertyDescriptor(navigator, 'clipboard')

function setClipboard(writeText) {
  Object.defineProperty(navigator, 'clipboard', {
    value: writeText ? { writeText } : undefined, configurable: true,
  })
}

afterEach(() => {
  if (origClipboard) Object.defineProperty(navigator, 'clipboard', origClipboard)
  else delete navigator.clipboard
})

test('copies the value and shows a confirmation state', async () => {
  const writeText = vi.fn().mockResolvedValue()
  setClipboard(writeText)
  render(<CopyButton value="C8734" label="Copy LCSC code" />)
  fireEvent.click(screen.getByRole('button', { name: 'Copy LCSC code' }))
  expect(writeText).toHaveBeenCalledWith('C8734')
  await waitFor(() => expect(screen.getByText('✓')).toBeInTheDocument())
})

test('renders nothing when the clipboard API is unavailable', () => {
  setClipboard(null)
  const { container } = render(<CopyButton value="C8734" />)
  expect(container).toBeEmptyDOMElement()
})
