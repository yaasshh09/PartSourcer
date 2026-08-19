import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import ContactPage from './ContactPage.jsx'
import { CONTACT } from '../contact.js'

const wrap = () => render(<MemoryRouter><ContactPage /></MemoryRouter>)

test('the email is a real mailto, not just text to copy by hand', () => {
  wrap()

  const link = screen.getByRole('link', { name: new RegExp(CONTACT.email, 'i') })

  expect(link).toHaveAttribute('href', `mailto:${CONTACT.email}`)
})

test('instagram opens the account, not the bare handle', () => {
  wrap()

  const link = screen.getByRole('link', { name: new RegExp(CONTACT.instagram, 'i') })

  expect(link).toHaveAttribute('href', CONTACT.instagramUrl)
})

test('points bug reports at issues, where they can be tracked', () => {
  wrap()

  const link = screen.getByRole('link', { name: /issue/i })

  expect(link).toHaveAttribute('href', CONTACT.issuesUrl)
})

test('every outbound link is safe to open in a new tab', () => {
  const { container } = wrap()

  for (const a of container.querySelectorAll('a[target="_blank"]')) {
    expect(a).toHaveAttribute('rel', expect.stringContaining('noreferrer'))
  }
})
