import { C, ARCHIVO, MONO, fmtPrice, fmtAsOf } from '../theme.js'
import { groupOffersByTier, DISTRIBUTOR_LABEL } from '../offers.js'
import StockBadge from './StockBadge.jsx'
import CopyButton from './CopyButton.jsx'

// The link column has no visible heading, but the column still needs a name
// for anyone reading the table through a screen reader. Clipped to nothing
// rather than parked off to the left, which can widen the page.
const SR_ONLY = {
  position: 'absolute', width: 1, height: 1, padding: 0, margin: -1,
  overflow: 'hidden', clip: 'rect(0 0 0 0)', whiteSpace: 'nowrap', border: 0,
}

const TH = {
  textAlign: 'left', fontFamily: ARCHIVO, fontWeight: 900, fontSize: 11,
  letterSpacing: '0.06em', color: C.sub, padding: '0 12px 10px 0',
  borderBottom: `3px solid ${C.ink}`,
}
const TD = {
  padding: '12px 12px 12px 0', borderBottom: '1px solid #e8e4d4',
  fontSize: 14, verticalAlign: 'top',
}

function isClaimed(offer, cheapest) {
  return !!cheapest
    && cheapest.distributor === offer.distributor
    && cheapest.sku === offer.sku
}

function OfferRow({ offer, cheapest, showNote }) {
  const claimed = isClaimed(offer, cheapest)
  return (
    <tr>
      <td style={TD}>
        <span style={{ fontWeight: 700 }}>
          {DISTRIBUTOR_LABEL[offer.distributor] || offer.distributor}
        </span>
        {claimed ? (
          <div style={{ display: 'inline-block', background: C.yellow, fontSize: 11,
            fontWeight: 700, padding: '2px 7px', marginLeft: 8 }}>
            {`cheapest of ${cheapest.compared_sources} sources`}
          </div>
        ) : null}
        {showNote && offer.match_note ? (
          <div style={{ fontSize: 12, color: C.sub, fontWeight: 500, marginTop: 4 }}>
            {offer.match_note}
          </div>
        ) : null}
      </td>
      <td style={TD}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontFamily: MONO, fontSize: 13 }}>{offer.sku}</span>
          <CopyButton value={offer.sku} label={`Copy ${offer.sku}`} />
        </div>
      </td>
      <td style={TD}><StockBadge stock={offer.stock} /></td>
      <td style={{ ...TD, fontFamily: ARCHIVO, fontWeight: 900, fontSize: 17 }}>
        {fmtPrice(offer.price_usd)}
      </td>
      <td style={{ ...TD, fontSize: 12, color: C.muted, fontWeight: 600 }}>
        {fmtAsOf(offer.as_of)}
      </td>
      <td style={TD}>
        {/* Null for LCSC over jlcsearch, real for Mouser and DigiKey, so this
            cell is conditional per row rather than per table. */}
        {offer.product_url ? (
          <a href={offer.product_url} target="_blank" rel="noopener noreferrer"
            aria-label={`View ${offer.sku} on ${DISTRIBUTOR_LABEL[offer.distributor] || offer.distributor}`}
            style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 12, color: C.ink }}>
            View ↗
          </a>
        ) : null}
      </td>
    </tr>
  )
}

function Block({ title, offers, cheapest, showNote, caption }) {
  if (!offers.length) return null
  return (
    <div style={{ marginTop: 18 }}>
      <div style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 13 }}>{title}</div>
      {caption ? (
        <div style={{ fontSize: 13, color: C.sub, fontWeight: 500, margin: '6px 0 0' }}>
          {caption}
        </div>
      ) : null}
      {/* Six columns do not fit a phone. The table scrolls inside its own box
          so the page itself never scrolls sideways. */}
      <div style={{ overflowX: 'auto', marginTop: 12 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              {/* scope="col" is the point of using a real table: it is what
                  ties each cell to its column for a screen reader. */}
              <th scope="col" style={TH}>DISTRIBUTOR</th>
              <th scope="col" style={TH}>SKU</th>
              <th scope="col" style={TH}>STOCK</th>
              <th scope="col" style={TH}>UNIT PRICE</th>
              <th scope="col" style={TH}>AS OF</th>
              <th scope="col" style={TH}><span style={SR_ONLY}>LINK</span></th>
            </tr>
          </thead>
          <tbody>
            {offers.map((o) => (
              <OfferRow key={`${o.distributor}:${o.sku}`} offer={o}
                cheapest={cheapest} showNote={showNote} />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

/**
 * Every distributor listing for one part, with exact matches and packaging
 * variants kept in separate blocks so a cheaper reel cannot silently undercut
 * the tube the user searched for.
 */
export default function OfferTable({ offers, cheapest = null, unavailableReason = null }) {
  const { exact, packaging } = groupOffersByTier(offers)
  if (!exact.length && !packaging.length) return null

  return (
    <div style={{ border: `3px solid ${C.ink}`, background: C.paper, padding: 22, marginTop: 20 }}>
      <Block title="EXACT MATCH" offers={exact} cheapest={cheapest} showNote={false} />
      <Block title="DIFFERENT PACKAGING" offers={packaging} cheapest={null} showNote
        caption="Same part number, different packaging. These are not the same physical part, so check the reel or tube before you swap." />
      {!cheapest && unavailableReason ? (
        <div style={{ fontSize: 12, color: C.muted, fontWeight: 600, marginTop: 14 }}>
          {`No cheapest claim: ${unavailableReason}.`}
        </div>
      ) : null}
    </div>
  )
}
