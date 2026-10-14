import { useEffect, useState } from 'react'
import { getHistory } from '../api.js'
import { C, ARCHIVO, fmtUnit, fmtAsOf } from '../theme.js'

const W = 240, H = 44, PAD = 3

// x by time rather than index, so a night the recorder missed shows as a
// longer step instead of being quietly squeezed out.
function linePoints(points, key) {
  const t0 = Date.parse(points[0].at), t1 = Date.parse(points[points.length - 1].at)
  const vals = points.map((p) => p[key])
  const lo = Math.min(...vals), hi = Math.max(...vals)
  return points.map((p, i) => {
    const x = t1 > t0 ? PAD + ((Date.parse(p.at) - t0) / (t1 - t0)) * (W - 2 * PAD) : PAD + i
    const y = hi > lo ? H - PAD - ((p[key] - lo) / (hi - lo)) * (H - 2 * PAD) : H / 2
    return `${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ')
}

function Spark({ points, field, label, fmt, color }) {
  const vals = points.map((p) => p[field])
  const lo = Math.min(...vals), hi = Math.max(...vals)
  const name = lo === hi ? `${label} held at ${fmt(lo)}` : `${label} from ${fmt(lo)} to ${fmt(hi)}`
  return (
    <div style={{ flex: '1 1 240px' }}>
      <div style={{ fontSize: 12, fontWeight: 700, color: C.sub, marginBottom: 4 }}>{name}</div>
      <svg role="img" aria-label={name} viewBox={`0 0 ${W} ${H}`} width="100%" height={H}
        preserveAspectRatio="none" style={{ display: 'block', maxWidth: 480 }}>
        <polyline points={linePoints(points, field)} fill="none" stroke={color} strokeWidth="2"
          vectorEffect="non-scaling-stroke" />
      </svg>
    </div>
  )
}

const fmtStock = (n) => Number(n).toLocaleString()

// Hidden until there are two readings to draw between. One dot is not a
// trend, and a panel saying "nothing yet" on most parts is noise.
export default function PriceHistory({ mpnKey }) {
  const [points, setPoints] = useState(null)
  useEffect(() => {
    let live = true
    setPoints(null)
    getHistory(mpnKey).then((b) => { if (live) setPoints(b.points || []) },
      () => { if (live) setPoints(null) })
    return () => { live = false }
  }, [mpnKey])
  if (!points || points.length < 2) return null
  return (
    <div style={{ border: `3px solid ${C.ink}`, background: C.paper, padding: 22, marginTop: 20 }}>
      <div style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 13, paddingBottom: 12,
        borderBottom: `3px solid ${C.ink}`, marginBottom: 14 }}>PRICE HISTORY</div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 24 }}>
        <Spark points={points} field="price_usd" label="Price" fmt={fmtUnit} color={C.orange} />
        <Spark points={points} field="stock" label="Stock" fmt={fmtStock} color={C.ink} />
      </div>
      <div style={{ fontSize: 12, color: C.muted, fontWeight: 600, marginTop: 12 }}>
        {`${points.length} nightly LCSC readings since ${fmtAsOf(points[0].at)}. Other distributors are not recorded yet.`}
      </div>
    </div>
  )
}
