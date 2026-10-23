import { useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { encodeKey, prefetchPart } from '../api.js'
import { C, ARCHIVO, MONO } from '../theme.js'
import { DISTRIBUTOR_LABEL, headlineOffer, lcscOffer, lifecycleWarnings } from '../offers.js'
import StockBadge from './StockBadge.jsx'
import CopyButton from './CopyButton.jsx'
import Price from './Price.jsx'
import PinButton from './PinButton.jsx'

const HOVER_MS = 200
const BADGE = { padding: '3px 10px', fontSize: 12, fontWeight: 700 }
// Below these a week's change is noise, and a badge on most cards is none.
const PRICE_DROP_PCT = -5
const STOCK_FALL_PCT = -50

export default function ResultCard({ part, trend }) {
  const to = `/part/${encodeKey(part.mpn_key)}`
  const headline = headlineOffer(part)
  const lcsc = lcscOffer(part)
  const offerCount = (part.offers || []).length

  // Only LCSC carries these, and only when upstream actually set them, so a
  // Mouser-only part gets no tier badge rather than a made-up "Standard".
  let tier = null
  if (lcsc && lcsc.is_preferred) tier = 'Preferred'
  else if (lcsc && lcsc.is_basic) tier = 'Basic'

  // A pointer that rests on a card for a moment is about to click it. Passing
  // over on the way somewhere else costs nothing.
  const intent = useRef(null)
  const stop = () => { clearTimeout(intent.current); intent.current = null }
  const start = () => { stop(); intent.current = setTimeout(() => prefetchPart(part.mpn_key), HOVER_MS) }
  useEffect(() => stop, [])

  // A wrapping flex row, not two grid tracks: a track will not shrink below
  // its longest word, so a long MPN used to carry the price column off the
  // side of a phone. The price drops under the part instead.
  return (
    <div className="ps-enter" onMouseEnter={start} onMouseLeave={stop} onFocus={start} onBlur={stop}
      style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 20,
      padding: '20px 22px', border: `3px solid ${C.ink}`, boxShadow: `5px 5px 0 ${C.ink}`, background: C.paper }}>
      <div style={{ flex: '1 1 240px', minWidth: 0 }}>
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
          {/* Part numbers have no spaces to break at, so the long ones need
              explicit permission to wrap or they overflow the card. */}
          <Link className="ps-link" to={to} style={{ fontFamily: MONO, fontWeight: 600, fontSize: 19,
            color: C.ink, textDecoration: 'none', overflowWrap: 'anywhere' }}>{part.mpn}</Link>
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
          {lifecycleWarnings(part).map((w) => (
            <span key={w.distributor} style={{ ...BADGE, background: C.orange, color: '#fff' }}>
              {`${w.status} at ${DISTRIBUTOR_LABEL[w.distributor] || w.distributor}`}
            </span>
          ))}
          {/* Only a backend claim may be called cheapest. "checked" is
              load-bearing: compared_sources counts the distributors that
              answered, not the offers that carried a price, so a part only
              LCSC stocks would otherwise read as two prices compared. */}
          {part.cheapest ? (
            <span style={{ ...BADGE, background: C.yellow, color: C.ink }}>
              {`cheapest of ${part.cheapest.compared_sources} sources checked`}
            </span>
          ) : null}
          {/* History is LCSC only, so the badge says whose price moved: the
              headline above can be another distributor's. */}
          {trend && trend.price_pct != null && trend.price_pct <= PRICE_DROP_PCT ? (
            <span style={{ ...BADGE, background: '#38d17a', color: '#062c16' }}>
              {`LCSC price down ${-trend.price_pct}% this week`}
            </span>
          ) : null}
          {trend && trend.stock_pct != null && trend.stock_pct <= STOCK_FALL_PCT ? (
            <span style={{ ...BADGE, background: '#ffb02e', color: '#3a2500' }}>
              {`LCSC stock fell ${-trend.stock_pct}% this week`}
            </span>
          ) : null}
          {offerCount > 1 ? (
            <span style={{ ...BADGE, background: 'transparent', color: C.sub,
              border: '2px solid #d8d4c4' }}>{`${offerCount} offers`}</span>
          ) : null}
        </div>
      </div>
      <div style={{ textAlign: 'right', flex: '0 0 auto' }}>
        {headline ? (
          <div style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 26 }}>
            <Price value={headline.price_usd} size={14} />
          </div>
        ) : null}
        <Link className="ps-link" to={to} style={{ display: 'inline-block', fontSize: 12, fontWeight: 700, color: C.orange,
          marginTop: 6, textDecoration: 'none' }}>VIEW DETAIL →</Link>
        <div style={{ marginTop: 8 }}><PinButton mpnKey={part.mpn_key} /></div>
      </div>
    </div>
  )
}
