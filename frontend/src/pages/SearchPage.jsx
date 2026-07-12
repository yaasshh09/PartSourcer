import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { search } from '../api.js'
import { C, fmtAsOf } from '../theme.js'
import ResultCard from '../components/ResultCard.jsx'

const EXAMPLES = ['STM32F103', 'NE555', 'AMS1117']
const COMING_SOON = ['BOM bulk upload', 'Price history', 'Browse by category', 'Biggest savings this week']
const MONO = "'IBM Plex Mono',monospace"
const ARCHIVO = "'Archivo',sans-serif"

export default function SearchPage() {
  const [params, setParams] = useSearchParams()
  const q = params.get('q') || ''

  const [query, setQuery] = useState(q)
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(!!q)
  const [error, setError] = useState(null)
  const [submitted, setSubmitted] = useState('')
  const [asOf, setAsOf] = useState(null)
  const inputRef = useRef(null)

  useEffect(() => {
    if (!q) {
      setResults([]); setError(null); setSubmitted(''); setAsOf(null); setLoading(false)
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
        setAsOf(data.results[0]?.as_of || null)
        setSubmitted(q)
      })
      .catch((e) => { if (!cancelled) setError(e) })
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
        {[0, 0.15, 0.3].map((delay) => (
          <div key={delay} style={{ height: 96, border: `3px solid ${C.ink}`, background: '#f0eee2',
            marginBottom: 14, animation: 'ps-pulse 1s ease-in-out infinite', animationDelay: `${delay}s` }} />
        ))}
      </div>
    )
  } else if (error) {
    body = (
      <div style={{ border: `3px dashed ${C.ink}`, padding: '56px 28px', textAlign: 'center', background: C.paper }}>
        <div style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 30 }}>SEARCH HIT A SNAG</div>
        <div style={{ fontSize: 15, color: C.sub, fontWeight: 500, marginTop: 10 }}>
          {`Search is unavailable right now — ${error.detail}`}
        </div>
      </div>
    )
  } else if (q && results.length) {
    body = (
      <div>
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between',
          paddingBottom: 12, borderBottom: `3px solid ${C.ink}`, marginBottom: 18 }}>
          <div style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 14 }}>
            {`RESULTS — ${results.length} MATCHES`}
          </div>
          <div style={{ fontSize: 12, color: C.muted, fontWeight: 600 }}>
            {`stock & price as of ${fmtAsOf(asOf)}`}
          </div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {results.map((part) => <ResultCard key={part.lcsc} part={part} />)}
        </div>
      </div>
    )
  } else if (q) {
    body = (
      <div style={{ border: `3px dashed ${C.ink}`, padding: '56px 28px', textAlign: 'center', background: C.paper }}>
        <div style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 30 }}>NO PARTS FOUND</div>
        <div style={{ fontSize: 15, color: C.sub, fontWeight: 500, marginTop: 10 }}>
          Nothing matched &quot;<span style={{ fontFamily: MONO }}>{submitted}</span>&quot;. Check the MPN, or try a broader spec.
        </div>
      </div>
    )
  } else {
    body = (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 30 }}>
        <div style={{ borderTop: `3px solid ${C.ink}`, paddingTop: 26 }}>
          <div style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 14, color: C.orange }}>WHY PARTSOURCER</div>
          <p style={{ fontSize: 18, color: '#2a2822', fontWeight: 500, lineHeight: 1.5, maxWidth: 700, margin: '14px 0 0' }}>
            Finding a part that&apos;s <b>actually in stock</b>, at a fair price, with a footprint you can drop onto
            your board means tab-hopping across distributor sites for every line of your BOM. PartSourcer collapses
            that into one search — and points you to a cheaper equivalent when one genuinely exists.
          </p>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16 }}>
          {[
            { n: '1', title: 'Search a part', body: 'By manufacturer part number, LCSC code, or plain-text spec.' },
            { n: '2', title: 'See live stock & price', body: 'Package, stock, unit price and datasheet — all scannable.' },
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
            EQUIVALENT vs. SIMILAR — WE DON&apos;T BLUR THE LINE
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 22, marginTop: 16 }}>
            <div>
              <div style={{ fontWeight: 700, fontSize: 16, color: '#38d17a' }}>✓ Equivalent</div>
              <div style={{ fontSize: 14, fontWeight: 500, color: '#e6e2d4', marginTop: 6 }}>
                Same footprint, matching core specs, verified pin-compatible, in stock, and cheaper. Safe to swap.
              </div>
            </div>
            <div>
              <div style={{ fontWeight: 700, fontSize: 16, color: '#ffb02e' }}>≈ Similar part</div>
              <div style={{ fontSize: 14, fontWeight: 500, color: '#e6e2d4', marginTop: 6 }}>
                Close on specs, but pin-compatibility isn&apos;t confirmed. We show it clearly labelled — never as a drop-in.
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
        <h1 style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 60, lineHeight: 0.98,
          letterSpacing: '-0.035em', margin: '22px 0 0', maxWidth: 900 }}>
          FIND THE CHEAPEST IN-STOCK PART FOR YOUR PCB IN ONE SEARCH.
        </h1>
        <p style={{ fontSize: 18, color: '#4a4838', maxWidth: 560, margin: '20px 0 0', fontWeight: 500 }}>
          Live stock, price, footprint &amp; datasheet — plus one cheaper in-stock equivalent. No login. No paywall.
        </p>
        <form onSubmit={(e) => { e.preventDefault(); runSearch(query) }}
          style={{ display: 'flex', alignItems: 'center', maxWidth: 720, marginTop: 34,
            border: `3px solid ${C.ink}`, boxShadow: `7px 7px 0 ${C.ink}`, background: C.paper }}>
          <span style={{ paddingLeft: 20, fontSize: 20 }}>⌕</span>
          <input ref={inputRef} value={query} onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by MPN, LCSC #, or spec…"
            style={{ flex: 1, border: 'none', padding: '20px 16px', fontSize: 17, fontWeight: 500,
              background: 'transparent' }} />
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
