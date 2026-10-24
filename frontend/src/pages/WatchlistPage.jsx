import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { encodeKey, getPart } from '../api.js'
import { loadWatch, saveWatch, sinceAdded } from '../watch.js'
import { DISTRIBUTOR_LABEL } from '../offers.js'
import { C, ARCHIVO, MONO, fmtAsOf, fmtUnit, NO_PRICE, SHELL_MAX } from '../theme.js'
import NoticePanel from '../components/NoticePanel.jsx'
import useDocumentTitle from '../useDocumentTitle.js'

// A full list is fifty parts. Reading them all at once would be fifty
// upstream calls in one burst, so a few at a time.
const PARALLEL = 3

const muted = { color: C.muted, fontStyle: 'italic', fontWeight: 500 }

function priceText(p) { return p == null ? NO_PRICE : fmtUnit(p) }

function Then({ e }) {
  if (!e.distributor) return <span style={muted}>No listing to compare against when watched.</span>
  return (
    <span>
      {`${priceText(e.price_usd)} · ${(e.stock ?? 0).toLocaleString('en-US')} in stock at ${DISTRIBUTOR_LABEL[e.distributor] || e.distributor}`}
      {e.as_of ? <span style={{ color: C.sub, fontWeight: 500 }}>{` (read ${fmtAsOf(e.as_of)})`}</span> : null}
    </span>
  )
}

function Now({ e, row }) {
  if (!row || row.status === 'loading') return <span style={muted}>reading…</span>
  if (row.status === 'error') return <span style={{ color: C.alert, fontWeight: 700 }}>{`Could not read: ${row.detail}`}</span>
  const c = sinceAdded(e, row.part)
  if (!c.offer) {
    return <span style={muted}>{e.distributor ? `No longer listed at ${DISTRIBUTOR_LABEL[e.distributor] || e.distributor}.` : 'Nothing to compare.'}</span>
  }
  const moves = []
  if (c.priceDelta) moves.push(`${c.priceDelta > 0 ? 'up' : 'down'} ${fmtUnit(Math.abs(c.priceDelta))}`)
  if (c.stockDelta) moves.push(`${Math.abs(c.stockDelta).toLocaleString('en-US')} ${c.stockDelta > 0 ? 'more' : 'fewer'} in stock`)
  return (
    <span>
      {`${priceText(c.offer.price_usd)} · ${c.offer.stock.toLocaleString('en-US')} in stock`}
      {c.offer.as_of ? <span style={{ color: C.sub, fontWeight: 500 }}>{` (read ${fmtAsOf(c.offer.as_of)})`}</span> : null}
      <span style={{ display: 'block', fontWeight: 800 }}>{moves.length ? moves.join(', ') : 'no change'}</span>
    </span>
  )
}

export default function WatchlistPage() {
  useDocumentTitle('Watchlist')
  const [list, setList] = useState(loadWatch)
  const [rows, setRows] = useState({})

  useEffect(() => {
    let live = true
    const queue = list.map((e) => e.k)
    const worker = async () => {
      while (live && queue.length) {
        const k = queue.shift()
        setRows((r) => ({ ...r, [k]: { status: 'loading' } }))
        try {
          const d = await getPart(k)
          if (live) setRows((r) => ({ ...r, [k]: { status: 'ok', part: d.part } }))
        } catch (err) {
          if (live) setRows((r) => ({ ...r, [k]: { status: 'error', detail: err.detail || err.message } }))
        }
      }
    }
    for (let i = 0; i < Math.min(PARALLEL, queue.length); i++) worker()
    return () => { live = false }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  function remove(k) {
    const next = loadWatch().filter((e) => e.k !== k)
    saveWatch(next)
    setList(next)
  }

  return (
    <section style={{ maxWidth: SHELL_MAX, margin: '0 auto', padding: '56px 28px 70px' }}>
      <h1 style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 'clamp(30px, 9vw, 48px)',
        letterSpacing: '-0.03em', margin: 0 }}>WATCHLIST</h1>
      {!list.length ? (
        <div style={{ marginTop: 24 }}>
          <NoticePanel title="NOTHING WATCHED YET">
            Press ☆ Watch on a part page. The part is kept in this browser with its price and stock at
            that moment, and this page reads the same listing again so you can see what moved.
          </NoticePanel>
        </div>
      ) : (
        <>
          <p style={{ fontSize: 15, color: C.sub, fontWeight: 500, maxWidth: 640, margin: '12px 0 24px' }}>
            Kept in this browser only, no account. Each part is read again when this page opens and
            compared with the same distributor listing it had when you watched it.
          </p>
          <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: 12 }}>
            {list.map((e) => (
              <li key={e.k} aria-label={e.k} style={{ border: `3px solid ${C.ink}`, background: C.paper,
                padding: '14px 16px', display: 'flex', flexWrap: 'wrap', gap: '8px 20px', alignItems: 'flex-start' }}>
                <div style={{ flex: '1 1 180px', minWidth: 0 }}>
                  <Link to={`/part/${encodeKey(e.k)}`} style={{ fontFamily: MONO, fontSize: 15,
                    fontWeight: 700, overflowWrap: 'anywhere' }}>{e.mpn || e.k}</Link>
                  {e.added ? <div style={{ fontSize: 12, color: C.sub, marginTop: 4 }}>{`watched ${fmtAsOf(e.added)}`}</div> : null}
                </div>
                <div style={{ flex: '2 1 240px', fontSize: 13, fontWeight: 600, minWidth: 0 }}>
                  <div style={{ fontSize: 11, color: C.sub, fontWeight: 800 }}>THEN</div>
                  <Then e={e} />
                </div>
                <div style={{ flex: '2 1 240px', fontSize: 13, fontWeight: 600, minWidth: 0 }}>
                  <div style={{ fontSize: 11, color: C.sub, fontWeight: 800 }}>NOW</div>
                  <Now e={e} row={rows[e.k]} />
                </div>
                <button type="button" aria-label={`Stop watching ${e.k}`} onClick={() => remove(e.k)} className="ps-chip"
                  style={{ background: 'transparent', border: `2px solid ${C.ink}`, cursor: 'pointer',
                    fontSize: 12, padding: '2px 8px' }}>✕</button>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  )
}
