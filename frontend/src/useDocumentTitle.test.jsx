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

function Described({ title, meta }) {
  useDocumentTitle(title, meta)
  return null
}

describe('per-page description and canonical link', () => {
  test('a page can describe itself and name its canonical address, and puts things back after', () => {
    const tag = document.createElement('meta')
    tag.name = 'description'
    tag.content = 'site default'
    document.head.appendChild(tag)
    const { unmount } = render(<Described title="NE555P"
      meta={{ description: 'NE555P timer: stock and price', canonical: 'https://x.test/part/NE555P' }} />)
    expect(document.querySelector('meta[name="description"]').content).toBe('NE555P timer: stock and price')
    expect(document.querySelector('link[rel="canonical"]').href).toBe('https://x.test/part/NE555P')
    unmount()
    expect(document.querySelector('meta[name="description"]').content).toBe('site default')
    expect(document.querySelector('link[rel="canonical"]')).toBeNull()
    tag.remove()
  })
})
