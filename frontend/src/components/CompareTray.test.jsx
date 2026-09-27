import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, test, expect } from 'vitest'
import CompareTray from './CompareTray.jsx'
import { CompareProvider } from '../compare.jsx'

beforeEach(() => { localStorage.clear() })

function renderTray(keys, path = '/') {
  localStorage.setItem('ps-compare', JSON.stringify(keys))
  return render(
    <MemoryRouter initialEntries={[path]}><CompareProvider><CompareTray /></CompareProvider></MemoryRouter>)
}

test('hidden when nothing is pinned', () => {
  const { container } = renderTray([])
  expect(container).toBeEmptyDOMElement()
})

test('one part asks for another instead of offering a compare', () => {
  renderTray(['A'])
  expect(screen.getByText('A')).toBeInTheDocument()
  expect(screen.getByText(/pin one more/i)).toBeInTheDocument()
  expect(screen.queryByRole('link', { name: /compare/i })).toBeNull()
})

test('two parts link to the compare page', () => {
  renderTray(['A', 'LM358P/NOPB'])
  expect(screen.getByRole('link', { name: 'Compare (2)' }))
    .toHaveAttribute('href', '/compare?k=A&k=LM358P%2FNOPB')
})

test('a part can be taken out, and clear empties it', () => {
  renderTray(['A', 'B'])
  fireEvent.click(screen.getByRole('button', { name: 'Remove A from compare' }))
  expect(screen.queryByText('A')).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: 'Clear' }))
  expect(screen.queryByRole('complementary')).toBeNull()
})

test('stays out of the way on the compare page itself', () => {
  const { container } = renderTray(['A', 'B'], '/compare')
  expect(container).toBeEmptyDOMElement()
})
