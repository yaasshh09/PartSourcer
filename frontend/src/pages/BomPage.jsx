import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { encodeKey, getPart } from '../api.js'
import { MAX_LINES, STATE_LABEL, checkLine, parseBom, summarize, toCsv } from '../bom.js'
import { DISTRIBUTOR_LABEL } from '../offers.js'
import { C, ARCHIVO, MONO, SHELL_MAX, SHIPPING_NOTE, fmtAsOf, fmtPrice, fmtUnit } from '../theme.js'
import useDocumentTitle from '../useDocumentTitle.js'

const STORE_KEY = 'ps-bom'
const PARALLEL = 4
const EXAMPLE = 'NE555P, 2\nRC0603FR-0710KL, 50\nLM358P, 4\nAMS1117-3.3, 3'

// Browser storage can throw (private windows, blocked site data). The list is
// a convenience, so losing it is fine and breaking the page is not.
function load() { try { return localStorage.getItem(STORE_KEY) || '' } catch { return '' } }
function save(v) { try { localStorage.setItem(STORE_KEY, v) } catch { /* convenience only */ } }

const cell = { padding: '10px 12px', borderTop: '2px solid #e6e2d2', verticalAlign: 'top',
  fontSize: 14, fontWeight: 600, textAlign: 'left' }
const head = { ...cell, borderTop: 'none', color: C.sub, fontSize: 12, whiteSpace: 'nowrap' }
const muted = { color: C.muted, fontWeight: 500 }
const STATE_COLOR = { ok: '#1d7a45', short: C.orange, unpriced: C.muted, missing: C.orange,
  error: C.orange, loading: C.muted }

const chip = { background: 'transparent', border: `2px solid ${C.ink}`, fontWeight: 700,
  fontSize: 13, padding: '7px 13px' }

export default function BomPage() {
  useDocumentTitle('BOM check')
  const [params, setParams] = useSearchParams()
  const shared = params.get('list')
  const [text, setText] = useState(() => shared ?? load())
  const [rows, setRows] = useState([])
  const [notice, setNotice] = useState(null)
  const [linked, setLinked] = useState(false)
  const run = useRef(0)
  const fileRef = useRef(null)
  const opened = useRef(false)

  // A shared link checks on arrival, then leaves the address bar, so a
  // refresh after editing does not put the sender's list back.
  useEffect(() => {
    if (!shared || opened.current) return
    opened.current = true
    save(shared)
    check(shared)
    setParams({}, { replace: true })
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  function edit(v) { setText(v); save(v) }

  // Read in the browser and dropped into the box, so what gets checked is
  // always what is on screen. A BOM is a few kilobytes; a megabyte is not one.
  async function loadFile(e) {
    const file = e.target.files && e.target.files[0]
    e.target.value = ''
    if (!file) return
    if (file.size > 1_000_000) { setNotice('That file is over 1 MB, which is too big to be a parts list.'); return }
    setNotice(null)
    edit(await file.text())
  }

  // Four reads at a time, so a long list neither trips the rate limit in one
  // burst nor waits on each line in turn. A newer check drops older answers.
  function read(lines, indices) {
    const id = run.current
    const queue = [...indices]
    setRows((r) => r.map((row, i) => (indices.includes(i) ? { ...lines[i], state: 'loading' } : row)))
    const settle = (i, patch) => {
      if (run.current === id) setRows((r) => r.map((row, j) => (j === i ? { ...lines[i], ...patch } : row)))
    }
    const worker = async () => {
      while (queue.length) {
        const i = queue.shift()
        try {
          const { part } = await getPart(lines[i].mpn)
          settle(i, { ...checkLine(part, lines[i].qty), key: part.mpn_key })
        } catch (e) {
          settle(i, e && e.status === 404 ? { state: 'missing' }
            : { state: 'error', detail: (e && e.detail) || 'Request failed' })
        }
      }
    }
    for (let k = 0; k < Math.min(PARALLEL, queue.length); k++) worker()
  }

  function onCheck(e) {
    e.preventDefault()
    check(text)
  }

  function check(src) {
    const { lines, count, tooMany, missingMpn } = parseBom(src)
    if (missingMpn) {
      setNotice('That header row has no part number column. Name it MPN, or paste just part numbers and quantities.')
      setRows([])
      return
    }
    if (!count) { setNotice('Add at least one part number, one per line.'); setRows([]); return }
    if (tooMany) {
      setNotice(`That is ${count} parts. The check takes up to ${MAX_LINES} at a time, so split the list.`)
      setRows([])
      return
    }
    setNotice(null)
    run.current += 1
    const fresh = lines.map((l) => ({ ...l, state: 'loading' }))
    setRows(fresh)
    read(fresh, fresh.map((_, i) => i))
  }

  function retry() {
    read(rows.map(({ mpn, qty }) => ({ mpn, qty })),
      rows.map((r, i) => (r.state === 'error' ? i : -1)).filter((i) => i >= 0))
  }

  // Rebuilt from the checked lines rather than the raw paste, so designators
  // and extra columns stay behind. The header keeps an all-digit part number
  // from reading as a quantity when the link is opened.
  function copyLink() {
    const list = ['MPN,Qty', ...rows.map((r) => `${r.mpn},${r.qty}`)].join('\n')
    const url = `${window.location.origin}/bom?list=${encodeURIComponent(list)}`
    navigator.clipboard.writeText(url).then(() => {
      setLinked(true)
      setTimeout(() => setLinked(false), 1600)
    }).catch(() => {})
  }

  function download() {
    if (typeof URL === 'undefined' || !URL.createObjectURL) return
    const url = URL.createObjectURL(new Blob([toCsv(rows)], { type: 'text/csv' }))
    const a = document.createElement('a')
    a.href = url
    a.download = 'partsourcer-bom.csv'
    a.click()
    setTimeout(() => URL.revokeObjectURL(url), 0)
  }

  const sum = summarize(rows)
  const ok = sum.counts.ok || 0
  const busy = (sum.counts.loading || 0) > 0
  const others = ['short', 'unpriced', 'missing', 'error']
    .filter((s) => sum.counts[s]).map((s) => `${sum.counts[s]} ${STATE_LABEL[s]}`)

  return (
    <section style={{ maxWidth: SHELL_MAX, margin: '0 auto', padding: '56px 28px 70px' }}>
      <h1 style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 'clamp(30px, 9vw, 48px)',
        letterSpacing: '-0.03em', margin: 0 }}>BOM CHECK</h1>
      <p style={{ fontSize: 17, color: '#4a4838', fontWeight: 500, maxWidth: 640, margin: '14px 0 24px' }}>
        Paste a parts list, one part per line with a quantity. Each line is priced at that quantity
        using the distributor&apos;s own price breaks, and only lines that can actually be ordered go into
        the total.
      </p>

      <form onSubmit={onCheck} style={{ border: `3px solid ${C.ink}`, background: C.paper, padding: 20,
        boxShadow: `5px 5px 0 ${C.ink}` }}>
        <label htmlFor="bom-text" style={{ display: 'block', fontFamily: ARCHIVO, fontWeight: 900,
          fontSize: 13, marginBottom: 8 }}>PARTS LIST</label>
        <textarea id="bom-text" value={text} onChange={(e) => edit(e.target.value)} rows={8}
          spellCheck={false} placeholder={'NE555P, 2\nRC0603FR-0710KL, 50'}
          style={{ width: '100%', fontFamily: MONO, fontSize: 14, padding: 12, resize: 'vertical',
            border: `2px solid ${C.ink}`, background: C.bg }} />
        <div style={{ fontSize: 12, color: C.sub, fontWeight: 500, marginTop: 6 }}>
          {`Part number and quantity, split by a comma, tab or space. Up to ${MAX_LINES} parts. Pasting a spreadsheet with a header row? The MPN and Qty columns are found by name.`}
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginTop: 14 }}>
          <button type="submit" className="ps-press" style={{ background: C.orange, color: '#fff',
            fontFamily: ARCHIVO, fontWeight: 900, fontSize: 15, padding: '12px 22px',
            border: `3px solid ${C.ink}` }}>CHECK PRICES</button>
          <button type="button" className="ps-chip" onClick={() => edit(EXAMPLE)} style={chip}>
            Try an example
          </button>
          <button type="button" className="ps-chip" onClick={() => fileRef.current.click()} style={chip}>
            Load a CSV
          </button>
          <input ref={fileRef} type="file" accept=".csv,.tsv,.txt,text/csv,text/plain"
            aria-label="Load a CSV file" onChange={loadFile} style={{ display: 'none' }} />
          {text ? (
            <button type="button" className="ps-chip" style={chip}
              onClick={() => { edit(''); setRows([]); setNotice(null) }}>Clear</button>
          ) : null}
        </div>
      </form>

      {notice ? (
        <p role="alert" style={{ fontSize: 14, fontWeight: 700, color: C.orange, margin: '18px 0 0' }}>{notice}</p>
      ) : null}

      {rows.length ? (
        <>
          <div aria-live="polite" style={{ marginTop: 28, border: `3px solid ${C.ink}`, background: C.yellow,
            padding: '16px 20px', display: 'flex', flexWrap: 'wrap', gap: '10px 24px',
            alignItems: 'baseline', justifyContent: 'space-between' }}>
            <div>
              <div style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 15 }}>
                {busy ? `CHECKING ${rows.length - sum.counts.loading} OF ${rows.length}…`
                  : `${ok} of ${rows.length} lines can be ordered`.toUpperCase()}
              </div>
              <div style={{ fontSize: 13, color: '#3a3200', fontWeight: 600, marginTop: 4 }}>
                {others.length ? `Left out of the total: ${others.join(', ')}.` : 'Every line is in the total.'}
              </div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div data-testid="bom-total" style={{ fontFamily: MONO, fontWeight: 700, fontSize: 26 }}>
                {fmtPrice(Math.round(sum.total * 10000) / 10000) || '$0.00'}
              </div>
              {sum.asOf ? (
                <div style={{ fontSize: 12, color: '#3a3200', fontWeight: 600 }}>{`read ${fmtAsOf(sum.asOf)}`}</div>
              ) : null}
            </div>
          </div>
          <div style={{ fontSize: 12, color: C.muted, fontWeight: 600, margin: '8px 0 14px' }}>{SHIPPING_NOTE}</div>

          {!busy ? (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginBottom: 14 }}>
              {sum.counts.error ? (
                <button type="button" className="ps-chip" onClick={retry} style={chip}>Retry failed lines</button>
              ) : null}
              <button type="button" className="ps-chip" onClick={download} style={chip}>Download CSV</button>
              {navigator.clipboard && navigator.clipboard.writeText ? (
                <button type="button" className="ps-chip" onClick={copyLink} style={chip}>
                  {linked ? 'Link copied' : 'Copy link'}
                </button>
              ) : null}
            </div>
          ) : null}

          {/* Scrolls inside its own box so the page never scrolls sideways. */}
          <div style={{ overflowX: 'auto', border: `3px solid ${C.ink}`, background: C.paper }}>
            <table style={{ borderCollapse: 'collapse', width: '100%', minWidth: 760 }}>
              <thead>
                <tr>
                  {['Part', 'Qty', 'Status', 'From', 'Unit price', 'Line total', 'Note'].map((h) => (
                    <th key={h} scope="col" style={head}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.mpn}>
                    <td style={{ ...cell, fontFamily: MONO, whiteSpace: 'nowrap' }}>
                      {r.key ? <Link className="ps-link" to={`/part/${encodeKey(r.key)}`}>{r.mpn}</Link> : r.mpn}
                    </td>
                    <td style={cell}>{r.qty.toLocaleString('en-US')}</td>
                    <td style={{ ...cell, color: STATE_COLOR[r.state], whiteSpace: 'nowrap' }}>
                      {STATE_LABEL[r.state]}
                    </td>
                    <td style={cell}>
                      {r.state === 'ok' ? (
                        <>
                          {DISTRIBUTOR_LABEL[r.offer.distributor] || r.offer.distributor}
                          <div style={{ ...muted, fontFamily: MONO, fontSize: 12 }}>
                            {r.offer.product_url ? (
                              <a className="ps-link" href={r.offer.product_url} target="_blank"
                                rel="noopener noreferrer">{`${r.offer.sku} ↗`}</a>
                            ) : r.offer.sku}
                          </div>
                        </>
                      ) : <span style={muted}>-</span>}
                    </td>
                    <td style={{ ...cell, fontFamily: MONO }}>
                      {r.state === 'ok' ? fmtUnit(r.unit) : <span style={muted}>-</span>}
                    </td>
                    <td style={{ ...cell, fontFamily: MONO }}>
                      {r.state === 'ok' ? fmtPrice(Math.round(r.total * 10000) / 10000) : <span style={muted}>-</span>}
                    </td>
                    <td style={{ ...cell, ...muted, fontSize: 13 }}>
                      {r.state === 'ok' ? (r.note || '')
                        : r.state === 'short' ? `only ${r.bestStock.toLocaleString('en-US')} in stock`
                          : r.state === 'error' ? r.detail : ''}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}
    </section>
  )
}
