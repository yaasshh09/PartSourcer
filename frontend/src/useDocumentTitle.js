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
 */
export default function useDocumentTitle(title) {
  useEffect(() => {
    document.title = title ? `${title} · ${BASE}` : HOME
  }, [title])
}
