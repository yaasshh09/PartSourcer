import { Link } from 'react-router-dom'
import { C, fmtPrice } from '../theme.js'
import StockBadge from './StockBadge.jsx'

export default function ResultCard({ part }) {
  return (
    <Link to={`/part/${part.lcsc}`}
      style={{ display: 'grid', gridTemplateColumns: '1fr auto', alignItems: 'center', gap: 20,
        padding: '20px 22px', border: `3px solid ${C.ink}`, boxShadow: `5px 5px 0 ${C.ink}`, background: C.paper }}>
      <div>
        <div style={{ fontFamily: "'IBM Plex Mono',monospace", fontWeight: 600, fontSize: 19 }}>{part.mpn}</div>
        {part.description ? (
          <div style={{ fontSize: 13, color: C.sub, marginTop: 4, fontWeight: 500 }}>{part.description}</div>
        ) : null}
        <div style={{ display: 'flex', gap: 10, marginTop: 12 }}>
          <span style={{ background: C.ink, color: '#fff', padding: '3px 10px', fontSize: 12, fontWeight: 700 }}>{part.package}</span>
          <StockBadge stock={part.stock} />
        </div>
      </div>
      <div style={{ textAlign: 'right' }}>
        <div style={{ fontFamily: "'Archivo',sans-serif", fontWeight: 900, fontSize: 26 }}>{fmtPrice(part.price_usd)}</div>
        <div style={{ fontSize: 12, fontWeight: 700, color: C.orange, marginTop: 6 }}>VIEW DETAIL →</div>
      </div>
    </Link>
  )
}
