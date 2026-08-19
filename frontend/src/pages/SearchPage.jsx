import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { search } from '../api.js'
import { C, ARCHIVO, MONO, fmtAsOf } from '../theme.js'
import { oldestAsOf } from '../offers.js'
import ResultCard from '../components/ResultCard.jsx'
import SourceStatusBar from '../components/SourceStatusBar.jsx'
import NoticePanel from '../components/NoticePanel.jsx'
import Landing from '../components/Landing.jsx'
import { useWaking, WAKE_NOTICE } from '../useWaking.js'

const EXAMPLES = ['STM32F103', 'NE555', 'AMS1117']

const SKELETON_DELAYS = [0, 0.15, 0.3]

export default function SearchPage() {
  const [params, setParams] = useSearchParams()
  const q = params.get('q') || ''

  const [query, setQuery] = useState(q)
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(!!q)
  const [error, setError] = useState(null)
  const [submitted, setSubmitted] = useState('')
  const [asOf, setAsOf] = useState(null)
  const [sources, setSources] = useState([])
  const inputRef = useRef(null)
  const waking = useWaking(loading)

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
    search(q)
      .then((data) => {
        if (cancelled) return
        setResults(data.results)
        // Oldest, not first: a fast distributor must not make the page look
        // fresher than its stalest record.
        setAsOf(oldestAsOf(data.results))
        setSources(data.sources || [])
        setSubmitted(q)
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
    setParams({ q: t })
  }

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
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {results.map((p) => <ResultCard key={p.mpn_key} part={p} />)}
        </div>
      </div>
    )
  } else if (q) {
    body = (
      <NoticePanel title="NO PARTS FOUND">
        Nothing matched &quot;<span style={{ fontFamily: MONO }}>{submitted}</span>&quot;. Check the MPN, or try a broader spec.
      </NoticePanel>
    )
  } else {
    body = <Landing />
  }

  return (
    <div>
      <section style={{ maxWidth: 1120, margin: '0 auto', padding: '70px 28px 40px' }}>
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
          <button type="submit" style={{ background: C.orange, color: '#fff', fontFamily: ARCHIVO,
            fontWeight: 900, fontSize: 16, padding: '0 34px', border: 'none',
            borderLeft: `3px solid ${C.ink}`, alignSelf: 'stretch' }}>SEARCH</button>
        </form>
        <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 10, marginTop: 18, maxWidth: 720 }}>
          <span style={{ color: C.muted, fontWeight: 600, fontSize: 13 }}>Try:</span>
          {EXAMPLES.map((ex) => (
            <button key={ex} type="button" onClick={() => runSearch(ex)}
              style={{ cursor: 'pointer', fontFamily: MONO, fontSize: 13, background: C.paper,
                border: `2px solid ${C.ink}`, padding: '5px 11px' }}>{ex}</button>
          ))}
          <span style={{ marginLeft: 'auto', color: C.muted, fontWeight: 600, fontSize: 13 }}>
            Press <kbd style={{ fontFamily: MONO, background: C.paper, border: `2px solid ${C.ink}`,
              borderBottomWidth: 3, padding: '1px 8px' }}>/</kbd> to focus
          </span>
        </div>
      </section>
      <section style={{ maxWidth: 1120, margin: '0 auto', padding: '12px 28px 70px' }}>
        {body}
      </section>
    </div>
  )
}
