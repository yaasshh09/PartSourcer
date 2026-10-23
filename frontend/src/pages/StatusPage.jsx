import { useEffect, useState } from 'react'
import { getStatus } from '../api.js'
import { DISTRIBUTOR_LABEL, SOURCE_STATE_COPY } from '../offers.js'
import { C, ARCHIVO, fmtAsOf, SHELL_MAX } from '../theme.js'
import NoticePanel from '../components/NoticePanel.jsx'
import useDocumentTitle from '../useDocumentTitle.js'

const cell = { padding: '10px 14px', borderTop: '2px solid #e6e2d2', textAlign: 'left',
  fontSize: 14, fontWeight: 600, verticalAlign: 'top' }
const muted = { color: C.muted, fontStyle: 'italic', fontWeight: 500 }

function Answered({ d }) {
  if (d.configured === false) return <span style={muted}>not set up on this site</span>
  const bad = Object.values(d.problems).reduce((a, b) => a + b, 0)
  if (!d.ok && !bad) return <span style={muted}>no requests yet</span>
  return <>{`${Math.floor((100 * d.ok) / (d.ok + bad))}%`}</>
}

export default function StatusPage() {
  useDocumentTitle('Status')
  const [state, setState] = useState({ status: 'loading' })

  useEffect(() => {
    let live = true
    getStatus().then((data) => { if (live) setState({ status: 'ok', data }) },
      (e) => { if (live) setState({ status: 'error', detail: e.detail || e.message }) })
    return () => { live = false }
  }, [])

  let body
  if (state.status === 'loading') body = <p style={muted}>reading…</p>
  else if (state.status === 'error') body = <NoticePanel title="COULDN'T READ STATUS">{state.detail}</NoticePanel>
  else {
    const { data } = state
    body = (
      <>
        <p style={{ fontSize: 15, color: C.sub, fontWeight: 500, maxWidth: 680, margin: '12px 0 20px' }}>
          {`How each distributor answered the searches and part pages people actually opened: ${data.reads} reads in the past ${data.window_hours} hours. `}
          A read served from the cache is not counted again, and LCSC here means the jlcsearch snapshot, which syncs about once a day.
        </p>
        <div style={{ overflowX: 'auto', border: `3px solid ${C.ink}`, background: C.paper }}>
          <table style={{ borderCollapse: 'collapse', width: '100%' }}>
            <thead>
              <tr>
                {['Distributor', 'Answered', 'Problems', 'Last answered', 'Last problem'].map((h) => (
                  <th key={h} scope="col" style={{ ...cell, borderTop: 'none', fontSize: 12, color: C.sub }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.distributors.map((d) => {
                const problems = Object.entries(d.problems)
                  .map(([s, n]) => `${n} ${SOURCE_STATE_COPY[s] || s}`)
                return (
                  <tr key={d.distributor}>
                    <th scope="row" style={cell}>{DISTRIBUTOR_LABEL[d.distributor] || d.distributor}</th>
                    <td style={cell}><Answered d={d} /></td>
                    <td style={cell}>{problems.length ? problems.join(', ') : <span style={muted}>none</span>}</td>
                    <td style={cell}>{d.last_ok_at ? fmtAsOf(d.last_ok_at) : <span style={muted}>-</span>}</td>
                    <td style={cell}>{d.last_problem
                      ? `${SOURCE_STATE_COPY[d.last_problem.state] || d.last_problem.state}, ${fmtAsOf(d.last_problem.at)}`
                      : <span style={muted}>-</span>}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </>
    )
  }

  return (
    <section style={{ maxWidth: SHELL_MAX, margin: '0 auto', padding: '56px 28px 70px' }}>
      <h1 style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 'clamp(30px, 9vw, 48px)',
        letterSpacing: '-0.03em', margin: 0 }}>STATUS</h1>
      {body}
    </section>
  )
}
