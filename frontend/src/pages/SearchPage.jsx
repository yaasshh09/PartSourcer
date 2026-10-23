import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { search, getTrends } from '../api.js'
import { C, ARCHIVO, MONO, fmtAsOf, SHELL_MAX, SHIPPING_NOTE } from '../theme.js'
import { DISTRIBUTOR_LABEL, lcscOffer, oldestAsOf, precedence, sortByPrice } from '../offers.js'
import ResultCard from '../components/ResultCard.jsx'
import SourceStatusBar from '../components/SourceStatusBar.jsx'
import NoticePanel from '../components/NoticePanel.jsx'
import Landing from '../components/Landing.jsx'
import { useWaking, WAKE_NOTICE } from '../useWaking.js'
import useDocumentTitle from '../useDocumentTitle.js'

const EXAMPLES = ['STM32F103', 'NE555', 'AMS1117']

const SKELETON_DELAYS = [0, 0.15, 0.3]

const selectStyle = { fontWeight: 700, fontSize: 12, padding: '4px 6px', border: `2px solid ${C.ink}`,
  background: C.paper, color: C.ink }

// JLCPCB assembly charges a setup fee per Extended part, not per Basic or
// Preferred one. Only LCSC carries the flag, so a part with no LCSC listing
// cannot be shown to qualify and is hidden too.
const isJlcBasic = (p) => {
  const l = lcscOffer(p)
  return !!(l && (l.is_basic || l.is_preferred))
}

// Recent searches live in this browser only. Storage can throw (private
// windows, blocked site data), and losing the list is fine.
const RECENT_KEY = 'ps-recent'
const RECENT_MAX = 5
function loadRecent() {
  try {
    const v = JSON.parse(localStorage.getItem(RECENT_KEY))
    return Array.isArray(v) ? v.filter((s) => typeof s === 'string').slice(0, RECENT_MAX) : []
  } catch { return [] }
}
function saveRecent(list) { try { localStorage.setItem(RECENT_KEY, JSON.stringify(list)) } catch { /* convenience only */ } }

export default function SearchPage() {
  const [params, setParams] = useSearchParams()
  const q = params.get('q') || ''
  const byPrice = params.get('sort') === 'price'
  const basicOnly = params.get('basic') === '1'
  const stockOnly = params.get('stock') === '1'
  const pkg = params.get('pkg') || ''
  const dist = params.get('dist') || ''

  useDocumentTitle(q || null)

  const [query, setQuery] = useState(q)
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(!!q)
  const [error, setError] = useState(null)
  const [submitted, setSubmitted] = useState('')
  const [sentAs, setSentAs] = useState('')
  const [asOf, setAsOf] = useState(null)
  const [sources, setSources] = useState([])
  const [trends, setTrends] = useState({})
  const [recent, setRecent] = useState(loadRecent)
  const inputRef = useRef(null)
  const waking = useWaking(loading)

  // Only a search that found something is worth offering again.
  function remember(t) {
    setRecent((prev) => {
      const next = [t, ...prev.filter((s) => s.toLowerCase() !== t.toLowerCase())].slice(0, RECENT_MAX)
      saveRecent(next)
      return next
    })
  }
  function forget() { saveRecent([]); setRecent([]) }

  useEffect(() => {
    if (!q) {
      setResults([]); setError(null); setSubmitted(''); setAsOf(null)
      setSources([]); setLoading(false); setQuery('')
      return
    }
    setQuery(q)
    let cancelled = false
    setLoading(true)
    setError(null)
    setTrends({})
    search(q)
      .then((data) => {
        if (cancelled) return
        setResults(data.results)
        // Oldest, not first: a fast distributor must not make the page look
        // fresher than its stalest record.
        setAsOf(oldestAsOf(data.results))
        setSources(data.sources || [])
        setSubmitted(q)
        setSentAs(data.query || q)
        if (data.results.length) {
          remember(q)
          // Extra, so a failure costs the badges and nothing else.
          getTrends(data.results.map((p) => p.mpn_key))
            .then((b) => { if (!cancelled) setTrends(b.trends || {}) }, () => {})
        }
      })
      // Sources go with the results they describe. A failed search knows
      // nothing about distributor health, and keeping the previous answer
      // would let a stale warning outlive the results it came from.
      .catch((e) => { if (!cancelled) { setError(e); setSources([]) } })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [q])

  useEffect(() => {
    const onKey = (e) => {
      if (e.key !== '/') return
      const tag = document.activeElement && document.activeElement.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA') return
      e.preventDefault()
      inputRef.current && inputRef.current.focus()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  function runSearch(text) {
    const t = text.trim()
    if (!t) return
    setQuery(t)
    const next = { q: t }
    if (byPrice) next.sort = 'price'
    if (basicOnly) next.basic = '1'
    if (stockOnly) next.stock = '1'
    // A package belongs to the last query's parts; a distributor does not.
    if (dist) next.dist = dist
    setParams(next)
  }

  // Sorting reorders what is already on screen. It is a view of the same
  // read, so it never searches again, and it lives in the URL so a sorted
  // link opens sorted.
  function setSort(price) {
    const next = new URLSearchParams(params)
    if (price) next.set('sort', 'price')
    else next.delete('sort')
    setParams(next, { replace: true })
  }

  // Filters, like sorting, are a view of the page already read.
  function setFilter(name, value) {
    const next = new URLSearchParams(params)
    if (value) next.set(name, value)
    else next.delete(name)
    setParams(next, { replace: true })
  }

  const packages = [...new Set(results.map((p) => p.package).filter(Boolean))].sort()
  const dists = [...new Set(results.flatMap((p) => (p.offers || []).map((o) => o.distributor)))]
    .sort((a, b) => precedence(a) - precedence(b))
  const kept = results.filter((p) => (!basicOnly || isJlcBasic(p))
    && (!stockOnly || (p.offers || []).some((o) => o.in_stock))
    && (!pkg || p.package === pkg)
    && (!dist || (p.offers || []).some((o) => o.distributor === dist)))
  const hidden = results.length - kept.length
  const shown = byPrice ? sortByPrice(kept) : kept
  const sortButton = (active, label, onClick) => (
    <button type="button" className="ps-chip" aria-pressed={active} onClick={onClick}
      style={{ fontWeight: 700, fontSize: 12, padding: '5px 10px', border: `2px solid ${C.ink}`,
        background: active ? C.ink : 'transparent', color: active ? C.yellow : C.ink }}>
      {label}
    </button>
  )

  let body
  if (loading) {
    body = (
      <div>
        <div style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 14, paddingBottom: 12,
          borderBottom: `3px solid ${C.ink}`, marginBottom: 16 }}>SEARCHING…</div>
        {waking ? (
          <div style={{ fontSize: 14, color: C.sub, fontWeight: 500, marginBottom: 14 }}>
            {WAKE_NOTICE}
          </div>
        ) : null}
        {SKELETON_DELAYS.map((delay) => (
          <div key={delay} style={{ height: 96, border: `3px solid ${C.ink}`, background: '#f0eee2',
            marginBottom: 14, animation: 'ps-pulse 1s ease-in-out infinite', animationDelay: `${delay}s` }} />
        ))}
      </div>
    )
  } else if (error) {
    body = (
      <NoticePanel title="SEARCH HIT A SNAG">
        {`Search is unavailable right now: ${error.detail}`}
      </NoticePanel>
    )
  } else if (q && results.length) {
    body = (
      <div>
        <SourceStatusBar sources={sources} />
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between',
          paddingBottom: 12, borderBottom: `3px solid ${C.ink}`, marginBottom: 18 }}>
          {/* "showing", not a total. This is one page of what the backend
              fetched, and upstream holds more than it fetched, so a bare
              count would read as the number of parts that exist. */}
          <div style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 14 }}>
            {`SHOWING ${results.length} RESULTS`}
          </div>
          <div style={{ fontSize: 12, color: C.muted, fontWeight: 600 }}>
            {`stock & price as of ${fmtAsOf(asOf)}`}
          </div>
        </div>
        {sentAs.toLowerCase() !== submitted.trim().toLowerCase() ? (
          <div style={{ fontSize: 13, color: C.sub, fontWeight: 600, marginBottom: 12 }}>
            {'Searched as '}<span style={{ fontFamily: MONO }}>{sentAs}</span>{', the way LCSC lists it.'}
          </div>
        ) : null}
        <div role="group" aria-label="Sort and filter results" style={{ display: 'flex', flexWrap: 'wrap',
          alignItems: 'center', gap: 8, marginBottom: 16 }}>
          <span style={{ fontSize: 12, fontWeight: 700, color: C.sub }}>SORT</span>
          {sortButton(!byPrice, 'Best match', () => setSort(false))}
          {sortButton(byPrice, 'Price, low to high', () => setSort(true))}
          {sortButton(basicOnly, 'JLC Basic only', () => setFilter('basic', basicOnly ? '' : '1'))}
          {sortButton(stockOnly, 'In stock only', () => setFilter('stock', stockOnly ? '' : '1'))}
          {/* A shared link can name a package this read did not return, so
              the current value stays listed rather than silently vanishing. */}
          <select aria-label="Package" value={pkg} onChange={(e) => setFilter('pkg', e.target.value)} style={selectStyle}>
            <option value="">Any package</option>
            {(pkg && !packages.includes(pkg) ? [...packages, pkg] : packages).map((v) => <option key={v} value={v}>{v}</option>)}
          </select>
          <select aria-label="Distributor" value={dist} onChange={(e) => setFilter('dist', e.target.value)} style={selectStyle}>
            <option value="">Any distributor</option>
            {(dist && !dists.includes(dist) ? [...dists, dist] : dists).map((v) => <option key={v} value={v}>{DISTRIBUTOR_LABEL[v] || v}</option>)}
          </select>
          <span style={{ fontSize: 12, color: C.muted, fontWeight: 600, marginLeft: 'auto' }}>{SHIPPING_NOTE}</span>
        </div>
        {hidden ? (
          <div style={{ fontSize: 13, color: C.sub, fontWeight: 600, marginBottom: 14 }}>
            {`${hidden} of ${results.length} results hidden by the filters above.`}
            {basicOnly ? ' JLC Basic only hides parts that are Extended at JLCPCB or not listed on LCSC.' : ''}
          </div>
        ) : null}
        <div className="ps-results">
          {shown.map((p) => <ResultCard key={p.mpn_key} part={p} trend={trends[p.mpn_key]} />)}
        </div>
      </div>
    )
  } else if (q) {
    // Extra words narrow a search, so the first word alone is the obvious
    // retry. Browsing needs no exact spelling at all.
    const first = submitted.trim().split(/\s+/)[0]
    const shorter = first && first !== submitted.trim() ? first : null
    body = (
      <NoticePanel title="NO PARTS FOUND">
        Nothing matched &quot;<span style={{ fontFamily: MONO }}>{submitted}</span>&quot;. Check the MPN, or try a broader spec.
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 12, marginTop: 14 }}>
          {shorter ? (
            <button type="button" className="ps-chip" onClick={() => runSearch(shorter)}
              style={{ cursor: 'pointer', fontWeight: 700, fontSize: 13, background: C.paper,
                border: `2px solid ${C.ink}`, padding: '6px 12px' }}>{`Search "${shorter}"`}</button>
          ) : null}
          <Link className="ps-link" to="/browse" style={{ fontWeight: 700, fontSize: 14 }}>
            Browse by category
          </Link>
        </div>
      </NoticePanel>
    )
  } else {
    body = <Landing />
  }

  return (
    <div>
      <section style={{ maxWidth: SHELL_MAX, margin: '0 auto', padding: '70px 28px 40px' }}>
        <span style={{ display: 'inline-block', background: C.ink, color: C.yellow, fontWeight: 700,
          fontSize: 13, padding: '6px 12px' }}>FREE &amp; OPEN-SOURCE ✱ MIT</span>
        {/* Scales instead of breaking: at a flat 60px the word CHEAPEST alone
            is wider than a 320px phone, and a headline is the one place where
            hyphenating mid-word looks worse than shrinking. 13vw reaches 60px
            at about 460px wide, so anything desktop-sized is unchanged. */}
        <h1 style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 'clamp(38px, 13vw, 60px)',
          lineHeight: 0.98, letterSpacing: '-0.035em', margin: '22px 0 0', maxWidth: 900 }}>
          FIND THE CHEAPEST IN-STOCK PART FOR YOUR PCB IN ONE SEARCH.
        </h1>
        <p style={{ fontSize: 18, color: '#4a4838', maxWidth: 560, margin: '20px 0 0', fontWeight: 500 }}>
          Stock, price, footprint &amp; datasheet, plus one cheaper in-stock equivalent. No login. No paywall.
        </p>
        <form onSubmit={(e) => { e.preventDefault(); runSearch(query) }}
          style={{ display: 'flex', alignItems: 'center', maxWidth: 720, marginTop: 34,
            border: `3px solid ${C.ink}`, boxShadow: `7px 7px 0 ${C.ink}`, background: C.paper }}>
          <span style={{ paddingLeft: 20, fontSize: 20 }}>⌕</span>
          {/* minWidth 0 is what lets this shrink. A flex item will not go below
              its placeholder's width without it, which pushed the SEARCH button
              past the right edge of a phone and scrolled the whole page. */}
          <input ref={inputRef} value={query} onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by MPN, LCSC #, or spec…"
            style={{ flex: 1, minWidth: 0, border: 'none', padding: '20px 16px', fontSize: 17,
              fontWeight: 500, background: 'transparent' }} />
          <button type="submit" className="ps-press" style={{ background: C.orange, color: '#fff', fontFamily: ARCHIVO,
            fontWeight: 900, fontSize: 16, padding: '0 34px', border: 'none',
            borderLeft: `3px solid ${C.ink}`, alignSelf: 'stretch' }}>SEARCH</button>
        </form>
        <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 10, marginTop: 18, maxWidth: 720 }}>
          <span style={{ color: C.muted, fontWeight: 600, fontSize: 13 }}>Try:</span>
          {EXAMPLES.map((ex) => (
            <button key={ex} type="button" className="ps-chip" onClick={() => runSearch(ex)}
              style={{ cursor: 'pointer', fontFamily: MONO, fontSize: 13, background: C.paper,
                border: `2px solid ${C.ink}`, padding: '5px 11px' }}>{ex}</button>
          ))}
          <span style={{ marginLeft: 'auto', color: C.muted, fontWeight: 600, fontSize: 13 }}>
            Press <kbd style={{ fontFamily: MONO, background: C.paper, border: `2px solid ${C.ink}`,
              borderBottomWidth: 3, padding: '1px 8px' }}>/</kbd> to focus
          </span>
        </div>
        {recent.length ? (
          <div role="group" aria-label="Recent searches" style={{ display: 'flex', alignItems: 'center',
            flexWrap: 'wrap', gap: 10, marginTop: 10, maxWidth: 720 }}>
            <span style={{ color: C.muted, fontWeight: 600, fontSize: 13 }}>Recent:</span>
            {recent.map((r) => (
              <button key={r} type="button" className="ps-chip" onClick={() => runSearch(r)}
                style={{ cursor: 'pointer', fontFamily: MONO, fontSize: 13, background: 'transparent',
                  border: `2px dashed ${C.ink}`, padding: '4px 10px' }}>{r}</button>
            ))}
            <button type="button" onClick={forget}
              style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', fontSize: 13,
                fontWeight: 600, color: C.muted, textDecoration: 'underline' }}>Clear</button>
          </div>
        ) : null}
      </section>
      <section style={{ maxWidth: SHELL_MAX, margin: '0 auto', padding: '12px 28px 70px' }}>
        {body}
      </section>
    </div>
  )
}
