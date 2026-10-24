import { useEffect } from 'react'

const BASE = 'PartSourcer'
const HOME = 'PartSourcer: cheapest in-stock part in one search'

/**
 * Sets the tab title for a route.
 *
 * A single-page app never reloads, so without this every page keeps whatever
 * index.html shipped with. Five tabs open on five different parts all read
 * the same, and a bookmark or a back-button entry says nothing about where it
 * points. Pass null on the home page to get the full strapline back.
 *
 * meta.description and meta.canonical are for pages worth finding by search,
 * a part above all: search engines run the page's script and read both, and
 * each is put back as it was when the page goes.
 */
export default function useDocumentTitle(title, meta = {}) {
  const { description, canonical } = meta
  useEffect(() => {
    document.title = title ? `${title} · ${BASE}` : HOME
  }, [title])

  useEffect(() => {
    if (!description) return undefined
    let tag = document.querySelector('meta[name="description"]')
    const made = !tag
    if (made) {
      tag = document.createElement('meta')
      tag.name = 'description'
      document.head.appendChild(tag)
    }
    const before = tag.content
    tag.content = description
    return () => { if (made) tag.remove(); else tag.content = before }
  }, [description])

  useEffect(() => {
    if (!canonical) return undefined
    const link = document.createElement('link')
    link.rel = 'canonical'
    link.href = canonical
    document.head.appendChild(link)
    return () => link.remove()
  }, [canonical])
}
