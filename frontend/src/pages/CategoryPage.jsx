import { useEffect, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { browse, encodeKey, getCategories } from '../api.js'
import { C, ARCHIVO, MONO, fmtAsOf, SHELL_MAX } from '../theme.js'
import NoticePanel from '../components/NoticePanel.jsx'
import StockBadge from '../components/StockBadge.jsx'
import useDocumentTitle from '../useDocumentTitle.js'
import { useWaking, WAKE_NOTICE } from '../useWaking.js'

const box = { border: `2px solid ${C.ink}`, padding: '8px 10px', fontSize: 15,
  background: C.paper, minWidth: 0, fontFamily: 'inherit' }

function FilterField({ filter, value, onChange }) {
  if (filter.kind === 'bool') {
    return (
      <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 600,
        fontSize: 14, paddingBottom: 10 }}>
        <input type="checkbox" checked={value === 'true'}
          onChange={(e) => onChange(e.target.checked ? 'true' : '')} />
        {filter.label}
      </label>
    )
  }
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 6, fontWeight: 600,
      fontSize: 13, flex: '1 1 160px', minWidth: 0 }}>
      {filter.label}
      {filter.kind === 'choice' ? (
        <select value={value} onChange={(e) => onChange(e.target.value)} style={box}>
          <option value="">Any</option>
          {filter.choices.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
      ) : (
        <input value={value} onChange={(e) => onChange(e.target.value)} style={box}
          placeholder={filter.example ? `e.g. ${filter.example}` : ''} />
      )}
    </label>
  )
}

function Row({ row }) {
  return (
    <li style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px 18px',
      border: `3px solid ${C.ink}`, background: C.paper, padding: '12px 16px' }}>
      <div style={{ flex: '1 1 220px', minWidth: 0 }}>
        <Link to={`/part/${encodeKey(row.mpn_key)}`} style={{ fontFamily: MONO, fontWeight: 600,
          fontSize: 15, overflowWrap: 'anywhere' }}>{row.mpn}</Link>
        <div style={{ fontSize: 12, color: C.muted, fontWeight: 600, marginTop: 2 }}>
          {[row.lcsc, row.package].filter(Boolean).join(' · ')}
        </div>
      </div>
      <dl style={{ display: 'flex', flexWrap: 'wrap', gap: '4px 16px', margin: 0, flex: '2 1 300px' }}>
        {row.specs.map(([label, value]) => (
          <div key={label} style={{ fontSize: 13 }}>
            <dt style={{ display: 'inline', color: C.sub, fontWeight: 600 }}>{`${label}: `}</dt>
            <dd style={{ display: 'inline', margin: 0, fontWeight: 700,
              color: value === null ? C.muted : C.ink, fontStyle: value === null ? 'italic' : 'normal' }}>
              {value === null ? 'not listed' : value}
            </dd>
          </div>
        ))}
      </dl>
      <StockBadge stock={row.stock} />
    </li>
  )
}

export default function CategoryPage() {
  const { slug } = useParams()
  const [params, setParams] = useSearchParams()
  const filterKey = params.toString()
  // undefined while the schema loads, null when the slug is not a category.
  const [category, setCategory] = useState(undefined)
  const [schemaError, setSchemaError] = useState(null)
  const [draft, setDraft] = useState({})
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const waking = useWaking(loading || (category === undefined && !schemaError))

  useDocumentTitle(category ? `Browse ${category.label}` : 'Browse')

  useEffect(() => {
    let cancelled = false
    setCategory(undefined)
    setSchemaError(null)
    getCategories()
      .then((d) => { if (!cancelled) setCategory(d.categories.find((c) => c.slug === slug) || null) })
      .catch((e) => { if (!cancelled) setSchemaError(e) })
    return () => { cancelled = true }
  }, [slug])

  // The form mirrors the URL, so Back and a shared link both restore it.
  useEffect(() => {
    setDraft(Object.fromEntries(new URLSearchParams(filterKey)))
  }, [filterKey])

  useEffect(() => {
    if (!category) return undefined
    let cancelled = false
    setLoading(true)
    setError(null)
    browse(slug, Object.fromEntries(new URLSearchParams(filterKey)))
      .then((d) => { if (!cancelled) setData(d) })
      .catch((e) => { if (!cancelled) { setError(e); setData(null) } })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [category, slug, filterKey])

  function apply(e) {
    e.preventDefault()
    setParams(Object.fromEntries(Object.entries(draft)
      .map(([k, v]) => [k, String(v).trim()])
      .filter(([, v]) => v)))
  }

  let content
  if (schemaError) {
    content = <NoticePanel title="BROWSE IS UNAVAILABLE">{`Could not load the categories: ${schemaError.detail}`}</NoticePanel>
  } else if (category === undefined) {
    content = (
      <div style={{ fontWeight: 600, color: C.sub, marginTop: 24 }}>
        Loading…
        {waking ? <div style={{ fontSize: 14, marginTop: 10 }}>{WAKE_NOTICE}</div> : null}
      </div>
    )
  } else if (category === null) {
    content = (
      <NoticePanel title="NO SUCH CATEGORY">
        There is no category called &quot;<span style={{ fontFamily: MONO }}>{slug}</span>&quot;.{' '}
        <Link to="/browse" style={{ textDecoration: 'underline' }}>See all categories</Link>.
      </NoticePanel>
    )
  } else {
    let results
    if (loading) {
      results = (
        <div style={{ fontWeight: 600, color: C.sub }}>
          Finding parts…
          {waking ? <div style={{ fontSize: 14, marginTop: 10 }}>{WAKE_NOTICE}</div> : null}
        </div>
      )
    } else if (error) {
      results = <NoticePanel title="COULD NOT BROWSE THAT" variant="inline">{error.detail}</NoticePanel>
    } else if (data && data.results.length === 0) {
      results = <NoticePanel title="NO PARTS MATCH" variant="inline">No parts match. Try a different package or value.</NoticePanel>
    } else if (data) {
      results = (
        <div>
          <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', justifyContent: 'space-between',
            gap: 8, paddingBottom: 12, borderBottom: `3px solid ${C.ink}`, marginBottom: 16 }}>
            <div style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 14 }}>
              {data.capped ? `${data.count} PARTS FROM THE TOP 100 BY STOCK` : `${data.count} PARTS`}
            </div>
            <div style={{ fontSize: 12, color: C.muted, fontWeight: 600 }}>
              {`stock from the LCSC snapshot, read ${fmtAsOf(data.as_of)}`}
            </div>
          </div>
          <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
            {/* Keyed by LCSC code: one MPN can carry several codes. */}
            {data.results.map((r) => <Row key={r.lcsc} row={r} />)}
          </ul>
        </div>
      )
    }
    content = (
      <>
        <h1 style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 'clamp(30px, 9vw, 48px)',
          letterSpacing: '-0.03em', margin: '14px 0 0' }}>{category.label.toUpperCase()}</h1>
        {category.note ? (
          <p style={{ fontSize: 15, color: C.sub, fontWeight: 500, maxWidth: 620, margin: '10px 0 0' }}>{category.note}</p>
        ) : null}
        <form onSubmit={apply} aria-label="Filters" style={{ display: 'flex', flexWrap: 'wrap', gap: 14,
          alignItems: 'flex-end', margin: '24px 0 28px', border: `3px solid ${C.ink}`,
          background: C.paper, padding: 18 }}>
          {category.filters.map((f) => (
            <FilterField key={f.name} filter={f} value={draft[f.name] || ''}
              onChange={(v) => setDraft((d) => ({ ...d, [f.name]: v }))} />
          ))}
          <button type="submit" style={{ background: C.orange, color: '#fff', fontFamily: ARCHIVO,
            fontWeight: 900, fontSize: 15, padding: '10px 26px', border: `3px solid ${C.ink}` }}>APPLY</button>
        </form>
        {results}
      </>
    )
  }

  return (
    <section style={{ maxWidth: SHELL_MAX, margin: '0 auto', padding: '40px 28px 70px' }}>
      <Link to="/browse" style={{ fontWeight: 600, fontSize: 14, color: C.sub }}>← All categories</Link>
      {content}
    </section>
  )
}
