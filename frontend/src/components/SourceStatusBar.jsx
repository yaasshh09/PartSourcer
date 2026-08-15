import { C } from '../theme.js'
import { degradedSources, DISTRIBUTOR_LABEL, SOURCE_STATE_COPY } from '../offers.js'

const ARCHIVO = "'Archivo',sans-serif"

/**
 * A notice, not a card: when a distributor did not answer, what is on screen
 * is an incomplete picture, and the user has to know that before treating a
 * price as the best available. Invisible when every source is healthy, so it
 * never becomes chrome people learn to skip.
 */
export default function SourceStatusBar({ sources }) {
  const degraded = degradedSources(sources)
  if (!degraded.length) return null

  const clauses = degraded.map((s) => {
    const who = DISTRIBUTOR_LABEL[s.distributor] || s.distributor
    // An unrecognised state still names itself rather than vanishing.
    const what = SOURCE_STATE_COPY[s.state] || s.state
    return `${who} ${what}`
  })

  return (
    <div role="status" style={{ border: `3px dashed ${C.ink}`, background: C.paper,
      padding: '14px 18px', marginBottom: 18 }}>
      <span style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 13 }}>
        Showing partial results:
      </span>
      <span style={{ fontSize: 14, fontWeight: 500, color: C.sub, marginLeft: 8 }}>
        {`${clauses.join(', ')}.`}
      </span>
    </div>
  )
}
