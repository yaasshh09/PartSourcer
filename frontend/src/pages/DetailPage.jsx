import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { getPart, getEquivalent } from '../api.js'
import { C, fmtPrice, fmtAsOf } from '../theme.js'
import StockBadge from '../components/StockBadge.jsx'
import CopyButton from '../components/CopyButton.jsx'
import DistributorLinks from '../components/DistributorLinks.jsx'

const MONO = "'IBM Plex Mono',monospace"
const ARCHIVO = "'Archivo',sans-serif"

export default function DetailPage() {
  const { lcsc } = useParams()

  const [part, setPart] = useState(null)
  const [equiv, setEquiv] = useState(null)
  const [equivError, setEquivError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    setPart(null); setEquiv(null); setEquivError(null); setLoading(true); setNotFound(false); setError(null)
    Promise.allSettled([getPart(lcsc), getEquivalent(lcsc)]).then(([p, e]) => {
      if (cancelled) return
      if (p.status === 'fulfilled') {
        setPart(p.value)
        if (e.status === 'fulfilled') setEquiv(e.value)
        else setEquivError(e.reason)
      } else if (p.reason && p.reason.status === 404) {
        setNotFound(true)
      } else {
        setError(p.reason)
      }
      setLoading(false)
    })
    return () => { cancelled = true }
  }, [lcsc])

  if (notFound) {
    return (
      <section style={{ maxWidth: 820, margin: '0 auto', padding: '90px 28px', textAlign: 'center' }}>
        <div style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 140, lineHeight: 1, color: C.orange }}>404</div>
        <div style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 30, marginTop: 8 }}>
          {"THIS PART ISN'T ON THE BOARD."}
        </div>
        <p style={{ fontSize: 16, color: C.sub, fontWeight: 500, marginTop: 12 }}>
          {"We couldn't find that part. Let's get you back to searching."}
        </p>
        <Link to="/" style={{ display: 'inline-block', marginTop: 22, background: C.ink, color: C.yellow,
          fontFamily: ARCHIVO, fontWeight: 900, fontSize: 15, padding: '14px 26px',
          border: `3px solid ${C.ink}`, boxShadow: `6px 6px 0 ${C.orange}`, textDecoration: 'none' }}>
          ← BACK TO SEARCH
        </Link>
      </section>
    )
  }

  if (loading) {
    return (
      <section style={{ maxWidth: 1120, margin: '0 auto', padding: '34px 28px 70px' }}>
        <div style={{ height: 140, border: `3px solid ${C.ink}`, background: '#f0eee2',
          animation: 'ps-pulse 1s ease-in-out infinite' }} />
        <div style={{ marginTop: 14, fontSize: 14, color: C.muted, fontWeight: 600 }}>Loading…</div>
      </section>
    )
  }

  if (error) {
    return (
      <section style={{ maxWidth: 1120, margin: '0 auto', padding: '34px 28px 70px' }}>
        <div style={{ border: `3px dashed ${C.ink}`, padding: '56px 28px', textAlign: 'center', background: C.paper }}>
          <div style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 30 }}>{"COULDN'T LOAD THIS PART"}</div>
          <div style={{ fontSize: 15, color: C.sub, fontWeight: 500, marginTop: 10 }}>{error.detail}</div>
        </div>
      </section>
    )
  }

  if (!part) return null

  const specRows = [
    ['LCSC', part.lcsc],
    ['Package', part.package],
    ['Stock', Number(part.stock || 0).toLocaleString()],
    ['Unit price', fmtPrice(part.price_usd)],
    ['Type', part.is_preferred ? 'Preferred' : part.is_basic ? 'Basic' : 'Standard'],
  ]
  if (part.description) specRows.push(['Description', part.description])

  const eq = equiv && equiv.equivalent

  return (
    <section style={{ maxWidth: 1120, margin: '0 auto', padding: '34px 28px 70px' }}>
      <Link to="/" style={{ display: 'inline-block', fontWeight: 700, fontSize: 14, color: C.ink,
        textDecoration: 'none', marginBottom: 22 }}>← Back to results</Link>

      <div style={{ border: `3px solid ${C.ink}`, boxShadow: `7px 7px 0 ${C.ink}`, background: C.paper,
        padding: 28, display: 'grid', gridTemplateColumns: '1fr auto', gap: 24, alignItems: 'start' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontFamily: MONO, fontSize: 12, color: C.muted }}>{part.lcsc}</span>
            <CopyButton value={part.lcsc} label="Copy LCSC code" />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, margin: '8px 0 0' }}>
            <h1 style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 38, lineHeight: 1.05, margin: 0 }}>
              {part.mpn}
            </h1>
            <CopyButton value={part.mpn} label="Copy MPN" />
          </div>
          {part.description ? (
            <p style={{ fontSize: 15, color: '#4a4838', fontWeight: 500, margin: '10px 0 0' }}>{part.description}</p>
          ) : null}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 14 }}>
            <span style={{ background: C.ink, color: '#fff', fontSize: 12, fontWeight: 700,
              padding: '4px 11px' }}>{part.package}</span>
            <StockBadge stock={part.stock} />
          </div>
          <div style={{ marginTop: 16 }}>
            <DistributorLinks code={part.lcsc} />
          </div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 44, lineHeight: 1 }}>
            {fmtPrice(part.price_usd)}
          </div>
          <div style={{ fontSize: 12, color: C.muted, fontWeight: 600, marginTop: 6 }}>unit price</div>
        </div>
      </div>

      <div style={{ border: `3px solid ${C.ink}`, background: C.paper, padding: 22, marginTop: 20 }}>
        <div style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 13, paddingBottom: 12,
          borderBottom: `3px solid ${C.ink}` }}>SPECIFICATIONS</div>
        {specRows.map(([key, value]) => (
          <div key={key} style={{ display: 'flex', justifyContent: 'space-between', gap: 16,
            padding: '11px 0', borderBottom: '1px solid #e8e4d4', fontSize: 14 }}>
            <span style={{ color: C.sub, fontWeight: 500 }}>{key}</span>
            <span style={{ fontWeight: 700, fontFamily: MONO, textAlign: 'right' }}>{value}</span>
          </div>
        ))}
        <div style={{ fontSize: 12, color: C.muted, fontWeight: 600, marginTop: 12 }}>
          {`stock & price as of ${fmtAsOf(part.as_of)}`}
        </div>
      </div>

      {eq ? (
        <div style={{ marginTop: 24, border: `3px solid ${C.ink}`, boxShadow: `10px 10px 0 ${C.orange}`,
          background: C.yellow, padding: 30 }}>
          <div style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 16 }}>
            <span aria-hidden="true">💡 </span>CHEAPER EQUIVALENT FOUND
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 30, alignItems: 'center',
            justifyContent: 'space-between', marginTop: 18 }}>
            <div style={{ flex: '1 1 260px', minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontFamily: MONO, fontSize: 12, color: '#5a4d1a' }}>{eq.lcsc}</span>
                <CopyButton value={eq.lcsc} label="Copy equivalent LCSC code" variant="onYellow" />
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 4 }}>
                <div style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 28 }}>{eq.mpn}</div>
                <CopyButton value={eq.mpn} label="Copy equivalent MPN" variant="onYellow" />
              </div>
              <div style={{ fontSize: 14, color: '#3a3200', fontWeight: 600, marginTop: 8 }}>
                {`${eq.package} · ${Number(eq.stock || 0).toLocaleString()} in stock · ${fmtPrice(eq.price_usd)}`}
              </div>
              <div style={{ fontSize: 14, color: '#3a3200', fontWeight: 500, marginTop: 8, maxWidth: 440 }}>
                {eq.match_reason}
              </div>
              <div style={{ marginTop: 14 }}>
                <DistributorLinks code={eq.lcsc} variant="onYellow" context="equivalent" />
              </div>
            </div>
            <div style={{ textAlign: 'center', background: C.ink, color: C.yellow, padding: '18px 24px',
              flex: '0 0 auto' }}>
              <div style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 60, lineHeight: 1 }}>
                {`${eq.percent_cheaper}%`}
              </div>
              <div style={{ fontSize: 12, fontWeight: 700, marginTop: 4 }}>CHEAPER</div>
              <div style={{ fontFamily: MONO, fontSize: 13, color: C.bg, marginTop: 8 }}>
                {`${fmtPrice(part.price_usd)} → ${fmtPrice(eq.price_usd)}`}
              </div>
            </div>
          </div>
        </div>
      ) : equiv ? (
        <div style={{ marginTop: 24, border: `3px dashed ${C.ink}`, background: C.paper, padding: 28 }}>
          <div style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 16 }}>
            {"NO CHEAPER EQUIVALENT — AND WE WON'T FAKE ONE"}
          </div>
          <p style={{ fontSize: 14, color: '#4a4838', fontWeight: 500, maxWidth: 560, margin: '10px 0 0' }}>
            {equiv.reason}
          </p>
        </div>
      ) : equivError ? (
        <div style={{ marginTop: 24, border: `3px dashed ${C.ink}`, background: C.paper, padding: 28 }}>
          <div style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 16 }}>
            EQUIVALENT CHECK UNAVAILABLE
          </div>
          <p style={{ fontSize: 14, color: '#4a4838', fontWeight: 500, maxWidth: 560, margin: '10px 0 0' }}>
            {`We couldn't check for a cheaper equivalent right now — ${equivError.detail}. Try refreshing in a moment.`}
          </p>
        </div>
      ) : null}
    </section>
  )
}
