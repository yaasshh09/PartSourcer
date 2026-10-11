import { useState } from 'react'
import { C, ARCHIVO, MONO, fmtAsOf, fmtPrice, fmtUnit, SHIPPING_NOTE } from '../theme.js'
import { groupOffersByTier, DISTRIBUTOR_LABEL } from '../offers.js'
import { priceAt } from '../bom.js'
import StockBadge from './StockBadge.jsx'
import CopyButton from './CopyButton.jsx'
import Price from './Price.jsx'

// The link column has no visible heading, but the column still needs a name
// for anyone reading the table through a screen reader. Clipped to nothing
// rather than parked off to the left, which can widen the page. See the note
// on TH for why the cell has to be its positioning context.
const SR_ONLY = {
  position: 'absolute', width: 1, height: 1, padding: 0, margin: -1,
  overflow: 'hidden', clip: 'rect(0 0 0 0)', whiteSpace: 'nowrap', border: 0,
}

// position: relative is load-bearing. The clipped LINK label below is
// absolutely positioned, and without a positioned ancestor it is laid out
// against the page rather than the cell, so on a phone it sat past the right
// edge of the screen and dragged the whole document sideways with it. The
// scroll box around the table cannot clip what was never inside it.
const TH = {
  textAlign: 'left', fontFamily: ARCHIVO, fontWeight: 900, fontSize: 11,
  letterSpacing: '0.06em', color: C.sub, padding: '0 12px 10px 0',
  borderBottom: `3px solid ${C.ink}`, position: 'relative',
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

// The quantity ladder a distributor published, folded away under the unit
// price. LCSC over jlcsearch sends none, and a single step says nothing the
// unit price does not, so both show no line at all.
function Breaks({ breaks }) {
  const steps = (breaks || []).filter((b) => b && b.qty > 0 && b.price_usd != null)
    .sort((a, b) => a.qty - b.qty)
  if (steps.length < 2) return null
  return (
    <details style={{ marginTop: 4, fontFamily: ARCHIVO, fontWeight: 600, fontSize: 12 }}>
      <summary style={{ cursor: 'pointer', color: C.sub }}>{`${steps.length} price breaks`}</summary>
      <table style={{ borderCollapse: 'collapse', marginTop: 4 }}>
        <tbody>
          {steps.map((b) => (
            <tr key={b.qty}>
              <td style={{ padding: '2px 12px 2px 0', color: C.sub }}>{`${b.qty.toLocaleString('en-US')}+`}</td>
              <td style={{ padding: '2px 0', fontFamily: MONO }}>{fmtUnit(b.price_usd)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  )
}

// What this listing costs for the quantity typed in, by the same rules the
// BOM check uses, so one quantity never costs two amounts on two pages.
function AtQty({ offer, qty }) {
  if (!qty) return null
  const p = priceAt(offer, qty)
  if (!p) return null
  const short = (offer.stock || 0) < p.orderQty
  return (
    <div style={{ marginTop: 4, fontFamily: ARCHIVO, fontWeight: 700, fontSize: 12 }}>
      <div>{`${p.orderQty.toLocaleString('en-US')} for ${fmtPrice(p.total)}`}</div>
      {p.note ? <div style={{ color: C.sub, fontWeight: 600 }}>{p.note}</div> : null}
      {short ? (
        <div style={{ color: C.orange }}>{`only ${(offer.stock || 0).toLocaleString('en-US')} in stock`}</div>
      ) : null}
    </div>
  )
}

function OfferRow({ offer, cheapest, showNote, qty }) {
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
            {`cheapest of ${cheapest.compared_sources} sources checked`}
          </div>
        ) : null}
        {showNote && offer.match_note ? (
          <div style={{ fontSize: 12, color: C.sub, fontWeight: 500, marginTop: 4 }}>
            {offer.match_note}
          </div>
        ) : null}
      </td>
      <td style={TD}>
        {/* A DigiKey product with no variation, and Mouser's literal "N/A",
            both arrive with no SKU. An empty cell reads as a fetch that
            failed, and there is nothing to put on the clipboard. */}
        {offer.sku ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontFamily: MONO, fontSize: 13 }}>{offer.sku}</span>
            <CopyButton value={offer.sku} label={`Copy ${offer.sku}`} />
          </div>
        ) : (
          <span style={{ fontFamily: ARCHIVO, fontWeight: 700, fontSize: 13,
            color: C.muted }}>no SKU</span>
        )}
      </td>
      <td style={TD}><StockBadge stock={offer.stock} /></td>
      <td style={{ ...TD, fontFamily: ARCHIVO, fontWeight: 900, fontSize: 17 }}>
        <Price value={offer.price_usd} />
        <Breaks breaks={offer.price_breaks} />
        <AtQty offer={offer} qty={qty} />
      </td>
      <td style={{ ...TD, fontSize: 12, color: C.muted, fontWeight: 600 }}>
        {fmtAsOf(offer.as_of)}
      </td>
      <td style={TD}>
        {/* Null for LCSC over jlcsearch, real for Mouser and DigiKey, so this
            cell is conditional per row rather than per table. */}
        {offer.product_url ? (
          <a className="ps-link" href={offer.product_url} target="_blank" rel="noopener noreferrer"
            aria-label={`View ${offer.sku} on ${DISTRIBUTOR_LABEL[offer.distributor] || offer.distributor}`}
            style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 12, color: C.ink }}>
            View ↗
          </a>
        ) : null}
      </td>
    </tr>
  )
}

function Block({ title, offers, cheapest, showNote, caption, qty }) {
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
                cheapest={cheapest} showNote={showNote} qty={qty} />
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
export default function OfferTable({ offers, cheapest = null, unavailableReason = null, initialQty = null }) {
  const [qtyText, setQtyText] = useState(initialQty || '')
  const { exact, packaging } = groupOffersByTier(offers)
  if (!exact.length && !packaging.length) return null
  const n = Number(qtyText)
  const qty = Number.isInteger(n) && n > 0 ? n : 0

  return (
    <div style={{ border: `3px solid ${C.ink}`, background: C.paper, padding: 22, marginTop: 20 }}>
      <label style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 10,
        fontFamily: ARCHIVO, fontWeight: 900, fontSize: 13 }}>
        PRICE FOR HOW MANY?
        <input type="number" min="1" step="1" inputMode="numeric" value={qtyText}
          onChange={(e) => setQtyText(e.target.value)} placeholder="e.g. 250"
          style={{ width: 120, fontFamily: MONO, fontSize: 14, padding: '6px 8px',
            border: `2px solid ${C.ink}`, background: C.bg }} />
      </label>
      <Block title="EXACT MATCH" offers={exact} cheapest={cheapest} showNote={false} qty={qty} />
      <Block title="DIFFERENT PACKAGING" offers={packaging} cheapest={null} showNote qty={qty}
        caption="Same part number, different packaging. These are not the same physical part, so check the reel or tube before you swap." />
      <div style={{ fontSize: 12, color: C.muted, fontWeight: 600, marginTop: 14 }}>{SHIPPING_NOTE}</div>
      {!cheapest && unavailableReason ? (
        <div style={{ fontSize: 12, color: C.muted, fontWeight: 600, marginTop: 14 }}>
          {`No cheapest claim: ${unavailableReason}.`}
        </div>
      ) : null}
    </div>
  )
}
