import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { encodeKey, getPart } from '../api.js'
import { cleanKeys, compareHref, rowLeaders, useCompare } from '../compare.jsx'
import { DISTRIBUTOR_LABEL, headlineOffer } from '../offers.js'
import { C, ARCHIVO, MONO, fmtAsOf, SHELL_MAX } from '../theme.js'
import NoticePanel from '../components/NoticePanel.jsx'
import Price from '../components/Price.jsx'
import useDocumentTitle from '../useDocumentTitle.js'

const cell = { padding: '12px 14px', borderTop: '2px solid #e6e2d2', verticalAlign: 'top',
  fontSize: 14, fontWeight: 600, minWidth: 170 }
const muted = { color: C.muted, fontStyle: 'italic', fontWeight: 500 }
const mark = { display: 'inline-block', marginTop: 6, background: C.yellow, color: C.ink,
  fontSize: 11, fontWeight: 800, padding: '2px 7px' }

const NOT_LISTED = <span style={muted}>not listed</span>

// Each row reads one fact from a loaded part. i is the column index, for the marks.
const ROWS = [
  ['Package', (p) => p.package || NOT_LISTED],
  ['Brand', (p) => p.brand || NOT_LISTED],
  ['Price', (p, i, lead) => {
    const h = headlineOffer(p)
    if (!h) return NOT_LISTED
    return (
      <>
        <Price value={h.price_usd} />
        <span style={{ color: C.sub, fontWeight: 500 }}>{` at ${DISTRIBUTOR_LABEL[h.distributor] || h.distributor}`}</span>
        {lead.lowestPrice.has(i) ? <div><span style={mark}>lowest price here</span></div> : null}
      </>
    )
  }],
  ['Stock', (p, i, lead) => {
    const h = headlineOffer(p)
    if (!h) return NOT_LISTED
    return (
      <>
        {h.stock.toLocaleString('en-US')}
        {lead.mostStock.has(i) ? <div><span style={mark}>most stock here</span></div> : null}
      </>
    )
  }],
  ['Offers', (p) => String((p.offers || []).length)],
  ['Datasheet', (p) => (p.datasheet_url ? (
    <a href={p.datasheet_url} target="_blank" rel="noopener noreferrer"
      style={{ textDecoration: 'underline' }}>Datasheet ↗</a>) : NOT_LISTED)],
  ['Read at', (p) => (p.as_of ? fmtAsOf(p.as_of) : NOT_LISTED)],
]

export default function ComparePage() {
  useDocumentTitle('Compare')
  const compare = useCompare()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const keys = cleanKeys(params.getAll('k'))
  const keyString = keys.join('\n')
  const [cols, setCols] = useState({})
  const colsRef = useRef(cols)
  colsRef.current = cols

  // A bare /compare opens whatever is pinned, so the tray link and a typed
  // address land on the same page.
  useEffect(() => {
    if (!keys.length && compare && compare.keys.length) {
      navigate(compareHref(compare.keys), { replace: true })
    }
  }, [keyString]) // eslint-disable-line react-hooks/exhaustive-deps

  // The URL wins: a shared link replaces what this browser had pinned.
  useEffect(() => {
    if (keys.length && compare) compare.setAll(keys)
  }, [keyString]) // eslint-disable-line react-hooks/exhaustive-deps

  // Each part loads on its own, so one failure cannot blank the rest. A part
  // already on screen is kept when another column is removed.
  useEffect(() => {
    let cancelled = false
    const wanted = keyString ? keyString.split('\n') : []
    const kept = colsRef.current
    const need = wanted.filter((k) => !(kept[k] && kept[k].status === 'ok'))
    setCols(Object.fromEntries(wanted.map((k) => [k, need.includes(k) ? { status: 'loading' } : kept[k]])))
    for (const k of need) {
      getPart(k)
        .then((d) => { if (!cancelled) setCols((c) => ({ ...c, [k]: { status: 'ok', part: d.part } })) })
        .catch((e) => { if (!cancelled) setCols((c) => ({ ...c, [k]: { status: 'error', error: e } })) })
    }
    return () => { cancelled = true }
  }, [keyString])

  function removeColumn(k) {
    const rest = keys.filter((x) => x !== k)
    // Both, in the same tick: with only the navigate, removing the last
    // column would see the old tray and bounce straight back to it.
    if (compare) compare.remove(k)
    navigate(rest.length ? compareHref(rest) : '/compare', { replace: true })
  }

  const heading = (
    <h1 style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 'clamp(30px, 9vw, 48px)',
      letterSpacing: '-0.03em', margin: 0 }}>COMPARE</h1>
  )

  if (!keys.length) {
    return (
      <section style={{ maxWidth: SHELL_MAX, margin: '0 auto', padding: '56px 28px 70px' }}>
        {heading}
        <div style={{ marginTop: 24 }}>
          <NoticePanel title="NOTHING TO COMPARE YET">
            Pin two to four parts with the + Compare button on search results, browse lists or a part
            page, then open the tray at the bottom of the screen.
          </NoticePanel>
        </div>
      </section>
    )
  }

  const parts = keys.map((k) => (cols[k] && cols[k].status === 'ok' ? cols[k].part : null))
  const lead = rowLeaders(parts)

  return (
    <section style={{ maxWidth: SHELL_MAX, margin: '0 auto', padding: '56px 28px 70px' }}>
      {heading}
      <p style={{ fontSize: 15, color: C.sub, fontWeight: 500, maxWidth: 620, margin: '12px 0 24px' }}>
        Different parts, not equivalents. Check package and specs before swapping one for another.
        Prices and stock are read fresh when this page opens.
      </p>
      {keys.length < 2 ? (
        <p style={{ fontSize: 14, fontWeight: 600, margin: '0 0 16px' }}>Pin at least one more part to compare.</p>
      ) : null}
      {/* The table scrolls inside its own box so the page never scrolls sideways. */}
      <div style={{ overflowX: 'auto', border: `3px solid ${C.ink}`, background: C.paper }}>
        <table style={{ borderCollapse: 'collapse', width: '100%' }}>
          <thead>
            <tr>
              <th scope="col" style={{ ...cell, borderTop: 'none', minWidth: 110, textAlign: 'left',
                color: C.sub, fontSize: 12 }}>Part</th>
              {keys.map((k) => {
                const col = cols[k] || { status: 'loading' }
                return (
                  <th key={k} scope="col" style={{ ...cell, borderTop: 'none', textAlign: 'left' }}>
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, justifyContent: 'space-between' }}>
                      {col.status === 'ok' ? (
                        <Link to={`/part/${encodeKey(col.part.mpn_key)}`} style={{ fontFamily: MONO,
                          fontSize: 15, overflowWrap: 'anywhere' }}>{col.part.mpn}</Link>
                      ) : (
                        <span style={{ fontFamily: MONO, fontSize: 15, overflowWrap: 'anywhere' }}>{k}</span>
                      )}
                      <button type="button" aria-label={`Remove ${k}`} onClick={() => removeColumn(k)}
                        style={{ background: 'transparent', border: `2px solid ${C.ink}`, cursor: 'pointer',
                          fontSize: 12, padding: '1px 6px' }}>✕</button>
                    </div>
                    {col.status === 'error' ? (
                      <div style={{ fontSize: 12, color: C.orange, fontWeight: 700, marginTop: 6 }}>
                        {`Could not load: ${col.error.detail}`}
                      </div>
                    ) : null}
                  </th>
                )
              })}
            </tr>
          </thead>
          <tbody>
            {ROWS.map(([label, read]) => (
              <tr key={label}>
                <th scope="row" style={{ ...cell, minWidth: 110, textAlign: 'left', color: C.sub, fontSize: 12 }}>{label}</th>
                {keys.map((k, i) => {
                  const col = cols[k] || { status: 'loading' }
                  let body
                  if (col.status === 'ok') body = read(col.part, i, lead)
                  else if (col.status === 'error') body = <span style={muted}>unavailable</span>
                  else body = <span style={muted}>loading…</span>
                  return <td key={k} style={cell}>{body}</td>
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
