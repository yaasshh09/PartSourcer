import { Link } from 'react-router-dom'
import { C, fmtPrice } from '../theme.js'
import StockBadge from './StockBadge.jsx'
import CopyButton from './CopyButton.jsx'

export default function ResultCard({ part }) {
  const to = `/part/${part.lcsc}`
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', alignItems: 'center', gap: 20,
      padding: '20px 22px', border: `3px solid ${C.ink}`, boxShadow: `5px 5px 0 ${C.ink}`, background: C.paper }}>
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Link to={to} style={{ fontFamily: "'IBM Plex Mono',monospace", fontWeight: 600, fontSize: 19,
            color: C.ink, textDecoration: 'none' }}>{part.mpn}</Link>
          <CopyButton value={part.lcsc} label={`Copy ${part.lcsc}`} />
        </div>
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
        <Link to={to} style={{ display: 'inline-block', fontSize: 12, fontWeight: 700, color: C.orange,
          marginTop: 6, textDecoration: 'none' }}>VIEW DETAIL →</Link>
      </div>
    </div>
  )
}
