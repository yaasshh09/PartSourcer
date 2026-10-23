import { Fragment, useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { encodeKey, getEquivalent, getPart } from '../api.js'
import { MAX_LINES, STATE_LABEL, checkLine, compareSwap, lineNote, parseBom, shareList, summarize,
  summarizeSwaps, toCsv, lcscFacts, toJlcBom, jlcGaps, summarizeBaskets } from '../bom.js'
import { DISTRIBUTOR_LABEL } from '../offers.js'
import { C, ARCHIVO, MONO, SHELL_MAX, SHIPPING_NOTE, fmtAsOf, fmtPrice, fmtUnit } from '../theme.js'
import useDocumentTitle from '../useDocumentTitle.js'

const STORE_KEY = 'ps-bom'
const MAX_BOARDS = 100000

// Anything that is not a whole number of boards counts as one, so a stray
// keystroke never multiplies a list by zero or by a fraction.
const toBoards = (v) => {
  const n = Number(v)
  return Number.isInteger(n) && n >= 1 ? Math.min(n, MAX_BOARDS) : 1
}
const PARALLEL = 4
// A swap costs up to two reads per line, so half the check's width keeps a
// pass under the 60 a minute limit for a typical list.
const SWAP_PARALLEL = 2
// Used when a 429 carries no readable retry-after (it is hidden cross-origin).
const RETRY_WAIT_S = 10
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
  const [boards, setBoards] = useState(() => String(toBoards(params.get('boards'))))
  const [checkedBoards, setCheckedBoards] = useState(1)
  const [rows, setRows] = useState([])
  const [notice, setNotice] = useState(null)
  const [skipped, setSkipped] = useState([])
  const [linked, setLinked] = useState(false)
  const run = useRef(0)
  const fileRef = useRef(null)
  const opened = useRef(false)
  // Its own flag rather than a run bump on unmount: StrictMode's rehearsal
  // unmount would otherwise drop the check a shared link starts on arrival.
  const live = useRef(true)
  useEffect(() => { live.current = true; return () => { live.current = false } }, [])

  // A shared link checks on arrival, then leaves the address bar, so a
  // refresh after editing does not put the sender's list back.
  useEffect(() => {
    if (!shared || opened.current) return
    opened.current = true
    save(shared)
    check(shared, toBoards(params.get('boards')))
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
          settle(i, { ...checkLine(part, lines[i].qty), ...lcscFacts(part), key: part.mpn_key })
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
    check(text, toBoards(boards))
  }

  function check(src, n) {
    const { lines, count, tooMany, missingMpn, skipped: dropped } = parseBom(src)
    setSkipped(missingMpn ? [] : dropped)
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
    setCheckedBoards(n)
    const fresh = lines.map((l) => ({ mpn: l.mpn, per: l.qty, qty: l.qty * n, refs: l.refs, state: 'loading' }))
    setRows(fresh)
    read(fresh, fresh.map((_, i) => i))
  }

  // Also stops a swap pass, whose half-done lines go back to unchecked.
  function retry() {
    run.current += 1
    setRows((rs) => rs.map((r) => (r.swapState === 'checking' ? { ...r, swapState: undefined } : r)))
    read(rows.map(({ mpn, per, qty, refs }) => ({ mpn, per, qty, refs })),
      rows.map((r, i) => (r.state === 'error' ? i : -1)).filter((i) => i >= 0))
  }

  const swappable = (r) => (r.state === 'ok' || r.state === 'short') && r.key && r.swapState !== 'done'

  // Run on request only, so a plain check never spends the extra reads. The
  // drop-in is read back through /api/part and priced like its line; the
  // equivalent endpoint's own saving is at quantity 1 and is not used.
  function findSwaps() {
    run.current += 1
    const id = run.current
    const current = () => run.current === id && live.current
    const queue = rows.map((r, i) => (swappable(r) ? i : -1)).filter((i) => i >= 0)
    const patch = (i, p) => { if (current()) setRows((rs) => rs.map((r, j) => (j === i ? { ...r, ...p } : r))) }
    // A copy, because the workers start shifting the queue before React runs this.
    const picked = new Set(queue)
    setRows((rs) => rs.map((r, i) => (picked.has(i) ? { ...r, swapState: 'checking', swapResult: null } : r)))
    const lookup = async (row) => {
      const { equivalent } = await getEquivalent(row.key)
      if (!equivalent) return null
      const { part } = await getPart(equivalent.mpn_key)
      return compareSwap(row, part)
    }
    const worker = async () => {
      while (queue.length && current()) {
        const i = queue.shift()
        for (let tries = 0; ; tries++) {
          try {
            patch(i, { swapState: 'done', swapResult: await lookup(rows[i]) })
          } catch (e) {
            // One pause and one more try on a rate limit; anything else fails the line.
            if (e && e.status === 429 && tries === 0) {
              await new Promise((ok) => setTimeout(ok, (e.retryAfter ?? RETRY_WAIT_S) * 1000))
              if (current()) continue
            }
            patch(i, { swapState: 'failed' })
          }
          break
        }
      }
    }
    for (let k = 0; k < Math.min(SWAP_PARALLEL, queue.length); k++) worker()
  }

  // Rebuilt from the checked lines rather than the raw paste, so designators
  // and extra columns stay behind. Quantities stay per board, with the board
  // count beside them, so the receiver can change it.
  function copyLink(swaps) {
    const extra = checkedBoards > 1 ? `&boards=${checkedBoards}` : ''
    const list = shareList(rows, { swaps })
    const url = `${window.location.origin}/bom?list=${encodeURIComponent(list)}${extra}`
    navigator.clipboard.writeText(url).then(() => {
      setLinked(swaps ? 'swaps' : 'plain')
      setTimeout(() => setLinked(false), 1600)
    }).catch(() => {})
  }

  function download(swaps, jlc = false) {
    if (typeof URL === 'undefined' || !URL.createObjectURL) return
    const csv = jlc ? toJlcBom(rows) : toCsv(rows, { swaps })
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }))
    const a = document.createElement('a')
    a.href = url
    a.download = jlc ? 'jlcpcb-bom.csv' : swaps ? 'partsourcer-bom-with-swaps.csv' : 'partsourcer-bom.csv'
    a.click()
    setTimeout(() => URL.revokeObjectURL(url), 0)
  }

  const sum = summarize(rows)
  const ok = sum.counts.ok || 0
  const busy = (sum.counts.loading || 0) > 0
  const others = ['short', 'unpriced', 'missing', 'error']
    .filter((s) => sum.counts[s]).map((s) => `${sum.counts[s]} ${STATE_LABEL[s]}`)

  const swapRows = rows.filter((r) => r.swapState)
  const swapsBusy = swapRows.some((r) => r.swapState === 'checking')
  const swapsDone = swapRows.length > 0 && !swapsBusy
  const swapFailed = swapRows.filter((r) => r.swapState === 'failed').length
  const sw = summarizeSwaps(rows)
  const canSwap = !busy && !swapsBusy && rows.some(swappable)
  const money = (n) => fmtPrice(Math.round(n * 10000) / 10000)
  // The total is already the cheapest split. Each extra distributor is
  // another shipment, so when it takes more than one, say what one order costs.
  const bk = summarizeBaskets(rows)
  const splitAcross = new Set(rows.filter((r) => r.state === 'ok').map((r) => r.offer.distributor)).size
  const label = (d) => DISTRIBUTOR_LABEL[d] || d
  let basketNote = null
  if (splitAcross > 1) {
    const extra = bk.best ? Math.round((bk.best.total - sum.total) * 10000) / 10000 : 0
    basketNote = !bk.best
      ? `No single distributor carries every line, so this order is split across ${splitAcross}.`
      : extra > 0
        ? `All from ${label(bk.best.distributor)}: ${money(bk.best.total)}, ${money(extra)} more than splitting, but one order to ship.`
        : `All from ${label(bk.best.distributor)}: ${money(bk.best.total)}, the same as splitting.`
  }
  // JLCPCB places parts by designator, so a list pasted without any gets no
  // JLCPCB file rather than one that cannot be ordered from.
  const hasRefs = rows.some((r) => r.refs)
  const gaps = jlcGaps(rows)
  const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`
  // No fee figure: JLCPCB sets it and it changes, so the note only says one applies.
  const jlcNote = [
    gaps.extended ? `${plural(gaps.extended, 'extended part')}, each with a JLCPCB setup fee` : null,
    gaps.noCode ? `${plural(gaps.noCode, 'line')} ${gaps.noCode === 1 ? 'has' : 'have'} no LCSC code, so JLCPCB will ask you to pick one` : null,
    gaps.noRefs ? `${plural(gaps.noRefs, 'line')} ${gaps.noRefs === 1 ? 'has' : 'have'} no designators, which JLCPCB needs to place the part` : null,
  ].filter(Boolean)

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
          {`Part number and quantity, split by a comma, tab or space. Up to ${MAX_LINES} parts. Pasting a spreadsheet with a header row? The MPN and Qty columns are found by name, so KiCad, Altium and JLCPCB exports load as they are.`}
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginTop: 14 }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontFamily: ARCHIVO,
            fontWeight: 900, fontSize: 13 }}>
            BOARDS
            <input type="number" min={1} max={MAX_BOARDS} step={1} value={boards}
              onChange={(e) => setBoards(e.target.value)}
              style={{ width: 90, fontFamily: MONO, fontSize: 15, padding: '9px 10px',
                border: `2px solid ${C.ink}`, background: C.bg }} />
          </label>
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
              onClick={() => { edit(''); setRows([]); setNotice(null); setSkipped([]) }}>Clear</button>
          ) : null}
        </div>
      </form>

      {notice ? (
        <p role="alert" style={{ fontSize: 14, fontWeight: 700, color: C.orange, margin: '18px 0 0' }}>{notice}</p>
      ) : null}

      {/* A line dropped without a word would make the total look more
          complete than it is, so every skipped line is named. */}
      {skipped.length ? (
        <p role="status" style={{ fontSize: 13, fontWeight: 600, color: C.sub, margin: '14px 0 0' }}>
          {`Skipped ${skipped.length} line${skipped.length === 1 ? '' : 's'} with no part number we could pick out: `
            + `${skipped.slice(0, 3).map((l) => `"${l}"`).join(', ')}${skipped.length > 3 ? ' and more' : ''}. `
            + 'If a part number is all digits, start the list with a header row, MPN,Qty.'}
        </p>
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
          {!busy && basketNote ? (
            <div style={{ fontSize: 13, color: C.sub, fontWeight: 600, margin: '-6px 0 14px' }}>{basketNote}</div>
          ) : null}

          {!busy ? (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginBottom: 14 }}>
              {sum.counts.error ? (
                <button type="button" className="ps-chip" onClick={retry} style={chip}>Retry failed lines</button>
              ) : null}
              {canSwap ? (
                <button type="button" className="ps-chip" onClick={findSwaps} style={chip}>
                  {swapFailed ? 'Retry swap checks' : 'Find cheaper swaps'}
                </button>
              ) : null}
              <button type="button" className="ps-chip" onClick={() => download(false)} style={chip}>Download CSV</button>
              {hasRefs ? (
                <button type="button" className="ps-chip" onClick={() => download(false, true)} style={chip}>
                  Download JLCPCB BOM
                </button>
              ) : null}
              {navigator.clipboard && navigator.clipboard.writeText ? (
                <button type="button" className="ps-chip" onClick={() => copyLink(false)} style={chip}>
                  {linked === 'plain' ? 'Link copied' : 'Copy link'}
                </button>
              ) : null}
              {swapsDone && sw.saves + sw.fills ? (
                <>
                  <button type="button" className="ps-chip" onClick={() => download(true)} style={chip}>
                    Download CSV with swaps
                  </button>
                  {navigator.clipboard && navigator.clipboard.writeText ? (
                    <button type="button" className="ps-chip" onClick={() => copyLink(true)} style={chip}>
                      {linked === 'swaps' ? 'Link copied' : 'Copy link with swaps'}
                    </button>
                  ) : null}
                </>
              ) : null}
            </div>
          ) : null}
          {!busy && hasRefs && jlcNote.length ? (
            <p style={{ fontSize: 12, color: C.sub, fontWeight: 600, margin: '0 0 14px' }}>
              {`For the JLCPCB BOM: ${jlcNote.join('; ')}.`}
            </p>
          ) : null}

          {/* Beside the original total, never folded into it: the table and
              the total stay on the parts the user listed. */}
          {swapRows.length ? (
            <div aria-live="polite" style={{ border: `3px solid ${C.ink}`, background: C.paper,
              padding: '12px 16px', marginBottom: 14, fontSize: 14, fontWeight: 600 }}>
              {swapsBusy ? (
                <div style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 14 }}>
                  {`Checking swaps ${swapRows.length - swapRows.filter((r) => r.swapState === 'checking').length} of ${swapRows.length}…`}
                </div>
              ) : (
                <>
                  {sw.saves ? (
                    <div style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 16 }}>
                      {`${sw.saves} swap${sw.saves === 1 ? ' saves' : 's save'} ${money(sw.saving)} `
                        + `(${Math.round((100 * sw.saving) / sum.total)}%) on `
                        + `${checkedBoards > 1 ? `${checkedBoards.toLocaleString('en-US')} boards` : 'this board'}.`}
                    </div>
                  ) : null}
                  {sw.fills ? (
                    <div>
                      {`${sw.fills} short line${sw.fills === 1 ? '' : 's'} can be filled by an in-stock drop-in, `
                        + `adding ${money(sw.fillCost)}.`}
                    </div>
                  ) : null}
                  {!sw.saves && !sw.fills ? (
                    <div>{`No verified cheaper drop-ins for ${swapFailed ? 'the lines that could be checked' : 'these lines'}.`}</div>
                  ) : null}
                  {swapFailed ? (
                    <div style={{ color: C.orange }}>
                      {`${swapFailed} line${swapFailed === 1 ? '' : 's'} could not be checked for swaps.`}
                    </div>
                  ) : null}
                  <div style={{ ...muted, fontSize: 12, marginTop: 4 }}>
                    {`Swaps cover resistors and capacitors only.${sw.asOf ? ` Swap prices read ${fmtAsOf(sw.asOf)}.` : ''}`}
                  </div>
                </>
              )}
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
                  <Fragment key={r.mpn}>
                  <tr>
                    <td style={{ ...cell, fontFamily: MONO, whiteSpace: 'nowrap' }}>
                      {r.key ? <Link className="ps-link" to={`/part/${encodeKey(r.key)}?qty=${r.qty}`}>{r.mpn}</Link> : r.mpn}
                    </td>
                    <td style={cell}>
                      {r.qty.toLocaleString('en-US')}
                      {checkedBoards > 1 ? (
                        <div style={{ ...muted, fontSize: 12 }}>
                          {`${r.per.toLocaleString('en-US')} × ${checkedBoards.toLocaleString('en-US')}`}
                        </div>
                      ) : null}
                    </td>
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
                      {r.state === 'ok' ? (
                        <>
                          {r.note || ''}
                          {r.thin ? (
                            <div style={{ color: C.orange, fontWeight: 700 }}>
                              {lineNote({ ...r, note: null })}
                            </div>
                          ) : null}
                        </>
                      )
                        : r.state === 'short' ? `only ${r.bestStock.toLocaleString('en-US')} in stock`
                          : r.state === 'error' ? r.detail : ''}
                    </td>
                  </tr>
                  {r.swapResult ? (
                    <tr>
                      <td colSpan={7} style={{ ...cell, borderTop: 'none', paddingTop: 0 }}>
                        <div style={{ background: C.yellow, border: `2px solid ${C.ink}`, padding: '8px 12px',
                          display: 'flex', flexWrap: 'wrap', gap: '4px 14px', alignItems: 'baseline' }}>
                          <span style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 12 }}>
                            {r.swapResult.kind === 'saves' ? 'CHEAPER DROP-IN' : 'IN-STOCK DROP-IN'}
                          </span>
                          <Link className="ps-link" style={{ fontFamily: MONO }}
                            to={`/part/${encodeKey(r.swapResult.key)}?qty=${r.qty}`}>{r.swapResult.mpn}</Link>
                          <span style={{ ...muted, fontFamily: MONO, fontSize: 12 }}>
                            {`${DISTRIBUTOR_LABEL[r.swapResult.swap.offer.distributor] || r.swapResult.swap.offer.distributor} ${r.swapResult.swap.offer.sku}`}
                          </span>
                          <span style={{ fontFamily: MONO }}>
                            {`${money(r.swapResult.swap.total)} for ${r.swapResult.swap.orderQty.toLocaleString('en-US')}`}
                          </span>
                          <span style={{ color: STATE_COLOR.ok, fontWeight: 800 }}>
                            {r.swapResult.kind === 'saves'
                              ? `saves ${money(r.swapResult.saving)} (${r.swapResult.pct}%)` : 'in stock, fills this line'}
                          </span>
                        </div>
                      </td>
                    </tr>
                  ) : r.swapState === 'failed' ? (
                    <tr>
                      <td colSpan={7} style={{ ...cell, borderTop: 'none', paddingTop: 0, fontSize: 13,
                        color: C.orange }}>swap check failed</td>
                    </tr>
                  ) : null}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}
    </section>
  )
}
