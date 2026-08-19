import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { search } from '../api.js'
import { C, ARCHIVO, MONO, fmtAsOf } from '../theme.js'
import { oldestAsOf } from '../offers.js'
import ResultCard from '../components/ResultCard.jsx'
import SourceStatusBar from '../components/SourceStatusBar.jsx'
import NoticePanel from '../components/NoticePanel.jsx'
import { useWaking, WAKE_NOTICE } from '../useWaking.js'

const EXAMPLES = ['STM32F103', 'NE555', 'AMS1117']
const COMING_SOON = ['BOM bulk upload', 'Price history', 'Browse by category', 'Biggest savings this week']

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
        {[0, 0.15, 0.3].map((delay) => (
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
    body = (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 30 }}>
        <div style={{ borderTop: `3px solid ${C.ink}`, paddingTop: 26 }}>
          <div style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 14, color: C.orange }}>WHY PARTSOURCER</div>
          <p style={{ fontSize: 18, color: '#2a2822', fontWeight: 500, lineHeight: 1.5, maxWidth: 700, margin: '14px 0 0' }}>
            Finding a part that&apos;s <b>actually in stock</b>, at a fair price, with a footprint you can drop onto
            your board means tab-hopping across distributor sites for every line of your BOM. PartSourcer collapses
            that into one search, and points you to a cheaper equivalent when one genuinely exists.
          </p>
        </div>
        {/* auto-fit rather than three fixed columns: a grid track never shrinks
            below its content, so on a phone three of them overflowed the page.
            This drops to two columns, then one, as the room runs out. */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16 }}>
          {[
            { n: '1', title: 'Search a part', body: 'By manufacturer part number, LCSC code, or plain-text spec.' },
            { n: '2', title: 'See stock & price', body: 'Package, stock, unit price and datasheet, all scannable.' },
            { n: '3', title: 'Get a cheaper swap 💡', body: "One drop-in equivalent that's in stock and costs less.", accent: true },
          ].map((s) => (
            <div key={s.n} style={{ border: `3px solid ${C.ink}`, padding: 20,
              background: s.accent ? C.yellow : C.paper }}>
              <div style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 32, color: s.accent ? C.ink : C.orange }}>{s.n}</div>
              <div style={{ fontWeight: 700, fontSize: 16, marginTop: 10 }}>{s.title}</div>
              <div style={{ fontSize: 13, fontWeight: 500, marginTop: 6, color: s.accent ? '#3a3200' : C.sub }}>{s.body}</div>
            </div>
          ))}
        </div>
        <div style={{ border: `3px solid ${C.ink}`, background: C.ink, color: C.bg, padding: 26 }}>
          <div style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 14, color: C.yellow }}>
            EQUIVALENT OR NOTHING: WE DON&apos;T BLUR THE LINE
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 22, marginTop: 16 }}>
            <div>
              <div style={{ fontWeight: 700, fontSize: 16, color: '#38d17a' }}>✓ Equivalent</div>
              <div style={{ fontSize: 14, fontWeight: 500, color: '#e6e2d4', marginTop: 6 }}>
                Same package, matching core specs, well stocked, and confirmed cheaper on a second reading of both prices. Safe to swap.
              </div>
            </div>
            <div>
              <div style={{ fontWeight: 700, fontSize: 16, color: '#ffb02e' }}>✗ No match</div>
              <div style={{ fontSize: 14, fontWeight: 500, color: '#e6e2d4', marginTop: 6 }}>
                Close is not good enough. If we cannot verify a drop-in you get a plain no and the reason why, never a maybe.
              </div>
            </div>
          </div>
        </div>
        <div>
          <div style={{ color: C.muted, fontWeight: 700, fontSize: 13, letterSpacing: '0.06em' }}>COMING SOON</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginTop: 12 }}>
            {COMING_SOON.map((label) => (
              <span key={label} style={{ fontFamily: MONO, fontSize: 13, background: C.paper,
                border: `2px dashed ${C.ink}`, padding: '6px 12px', color: C.sub }}>{label}</span>
            ))}
          </div>
        </div>
      </div>
    )
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
