import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getCategories } from '../api.js'
import { C, ARCHIVO, SHELL_MAX } from '../theme.js'
import NoticePanel from '../components/NoticePanel.jsx'
import useDocumentTitle from '../useDocumentTitle.js'
import { useWaking, WAKE_NOTICE } from '../useWaking.js'

export default function BrowsePage() {
  useDocumentTitle('Browse')
  const [categories, setCategories] = useState(null)
  const [error, setError] = useState(null)
  const waking = useWaking(categories === null && !error)

  useEffect(() => {
    let cancelled = false
    getCategories()
      .then((d) => { if (!cancelled) setCategories(d.categories) })
      .catch((e) => { if (!cancelled) setError(e) })
    return () => { cancelled = true }
  }, [])

  let body
  if (error) {
    body = <NoticePanel title="BROWSE IS UNAVAILABLE">{`Could not load the categories: ${error.detail}`}</NoticePanel>
  } else if (!categories) {
    body = (
      <div style={{ fontWeight: 600, color: C.sub }}>
        Loading categories…
        {waking ? <div style={{ fontSize: 14, marginTop: 10 }}>{WAKE_NOTICE}</div> : null}
      </div>
    )
  } else {
    body = (
      <div style={{ display: 'grid', gap: 16,
        gridTemplateColumns: 'repeat(auto-fill, minmax(min(260px, 100%), 1fr))' }}>
        {categories.map((c) => (
          <Link key={c.slug} to={`/browse/${c.slug}`} className="ps-lift" style={{ display: 'block',
            border: `3px solid ${C.ink}`, background: C.paper, padding: 22,
            boxShadow: `5px 5px 0 ${C.ink}` }}>
            <div style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 24 }}>{c.label}</div>
            <div style={{ fontSize: 13.5, color: C.sub, fontWeight: 500, marginTop: 8 }}>
              {c.filters.length
                // Only the first letter drops: "Min Vds" must not become "min vds".
                ? `Filter by ${c.filters.map((f) => f.label[0].toLowerCase() + f.label.slice(1)).join(', ')}`
                : 'Most stocked first'}
            </div>
          </Link>
        ))}
      </div>
    )
  }

  return (
    <section style={{ maxWidth: SHELL_MAX, margin: '0 auto', padding: '56px 28px 70px' }}>
      <h1 style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 'clamp(30px, 9vw, 48px)',
        letterSpacing: '-0.03em', margin: 0 }}>BROWSE BY CATEGORY</h1>
      <p style={{ fontSize: 17, color: '#4a4838', fontWeight: 500, maxWidth: 620, margin: '14px 0 30px' }}>
        Know the spec but not the part number? Pick a category, filter by package and value,
        then open any part to see its price and whether a cheaper swap exists.
      </p>
      {body}
    </section>
  )
}
