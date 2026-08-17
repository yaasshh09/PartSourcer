import { Link } from 'react-router-dom'
import { encodeKey } from '../api.js'
import { C, ARCHIVO, MONO } from '../theme.js'
import { headlineOffer, lcscOffer } from '../offers.js'
import StockBadge from './StockBadge.jsx'
import CopyButton from './CopyButton.jsx'
import Price from './Price.jsx'

const BADGE = { padding: '3px 10px', fontSize: 12, fontWeight: 700 }

export default function ResultCard({ part }) {
  const to = `/part/${encodeKey(part.mpn_key)}`
  const headline = headlineOffer(part)
  const lcsc = lcscOffer(part)
  const offerCount = (part.offers || []).length

  // Only LCSC carries these, and only when upstream actually set them, so a
  // Mouser-only part gets no tier badge rather than a made-up "Standard".
  let tier = null
  if (lcsc && lcsc.is_preferred) tier = 'Preferred'
  else if (lcsc && lcsc.is_basic) tier = 'Basic'

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', alignItems: 'center', gap: 20,
      padding: '20px 22px', border: `3px solid ${C.ink}`, boxShadow: `5px 5px 0 ${C.ink}`, background: C.paper }}>
      <div>
        {/* Only Mouser carries a manufacturer, so this is present on most of a
            Mouser-heavy query and almost none of an LCSC-heavy one. Absent
            means no line, not a placeholder. */}
        {part.brand ? (
          <div data-testid="brand" style={{ fontSize: 11, fontWeight: 700, color: C.muted,
            letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 5 }}>
            {part.brand}
          </div>
        ) : null}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Link to={to} style={{ fontFamily: MONO, fontWeight: 600, fontSize: 19,
            color: C.ink, textDecoration: 'none' }}>{part.mpn}</Link>
          <CopyButton value={part.mpn} label={`Copy ${part.mpn}`} />
        </div>
        {part.description ? (
          <div style={{ fontSize: 13, color: C.sub, marginTop: 4, fontWeight: 500 }}>{part.description}</div>
        ) : null}
        <div style={{ display: 'flex', gap: 10, marginTop: 12, flexWrap: 'wrap' }}>
          {part.package ? (
            <span style={{ ...BADGE, background: C.ink, color: '#fff' }}>{part.package}</span>
          ) : null}
          {headline ? <StockBadge stock={headline.stock} /> : null}
          {tier ? (
            <span style={{ ...BADGE, background: 'transparent', color: C.sub,
              border: '2px solid #d8d4c4' }}>{tier}</span>
          ) : null}
          {/* Only a backend claim may be called cheapest. */}
          {part.cheapest ? (
            <span style={{ ...BADGE, background: C.yellow, color: C.ink }}>
              {`cheapest of ${part.cheapest.compared_sources} sources`}
            </span>
          ) : null}
          {offerCount > 1 ? (
            <span style={{ ...BADGE, background: 'transparent', color: C.sub,
              border: '2px solid #d8d4c4' }}>{`${offerCount} offers`}</span>
          ) : null}
        </div>
      </div>
      <div style={{ textAlign: 'right' }}>
        {headline ? (
          <div style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 26 }}>
            <Price value={headline.price_usd} size={14} />
          </div>
        ) : null}
        <Link to={to} style={{ display: 'inline-block', fontSize: 12, fontWeight: 700, color: C.orange,
          marginTop: 6, textDecoration: 'none' }}>VIEW DETAIL →</Link>
      </div>
    </div>
  )
}
