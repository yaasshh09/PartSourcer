import { describe, test, expect } from 'vitest'
import { render } from '@testing-library/react'
import useDocumentTitle from './useDocumentTitle.js'

function Page({ title }) {
  useDocumentTitle(title)
  return null
}

describe('useDocumentTitle', () => {
  test('suffixes the site name so a tab says where it points', () => {
    render(<Page title="FAQ" />)
    expect(document.title).toBe('FAQ · PartSourcer')
  })

  test('falls back to the full strapline on the home page', () => {
    render(<Page title={null} />)
    expect(document.title).toBe('PartSourcer: cheapest in-stock part in one search')
  })

  test('follows the title changing, which is what a part page does on load', () => {
    const { rerender } = render(<Page title="C7593" />)
    expect(document.title).toBe('C7593 · PartSourcer')

    rerender(<Page title="NE555P" />)
    expect(document.title).toBe('NE555P · PartSourcer')
  })
})
