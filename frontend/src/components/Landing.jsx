import { Link } from 'react-router-dom'
import { C, ARCHIVO, MONO } from '../theme.js'

/**
 * Everything the search page shows before anyone has searched.
 *
 * Lives apart from SearchPage because none of it depends on query state, and
 * a page that both fetches results and carries the whole pitch is two jobs in
 * one file. Nothing here fetches: the worked example is a labelled
 * illustration, not a reading, which is the only way to show concrete numbers
 * without freezing a price the project promises to keep honest.
 */

const STEPS = [
  { n: '1', title: 'Search a part', body: 'By manufacturer part number, LCSC code, or plain-text spec.' },
  { n: '2', title: 'See stock & price', body: 'Package, stock, unit price and datasheet, all scannable.' },
  { n: '3', title: 'Get a cheaper swap 💡', body: "One drop-in equivalent that's in stock and costs less.", accent: true },
]

const PRINCIPLES = [
  {
    title: 'Never fake stock or price',
    body: 'Every figure carries the moment it was read and the page prints it. If the upstream is down and the cache has gone stale, you get an error instead of yesterday’s number wearing today’s date.',
  },
  {
    title: 'Never overstate a match',
    body: 'Package and core specs have to genuinely line up before anything is called an equivalent. Where that cannot be verified you get a plain no and the reason for it.',
  },
  {
    title: 'Never compare prices fetched differently',
    body: 'Distributors answer with different numbers depending how you ask. Both halves of a saving are re-read on one single path first, so the percentage means something.',
  },
  {
    title: 'Never invent a price',
    body: 'A distributor that published nothing hands back nothing, not zero. A zero would read as free and would win the cheapest comparison outright, so it is left out and labelled.',
  },
]

const AUDIENCE = [
  { title: 'Hobbyists', body: 'One-off boards, no contract pricing, and a real need for the stock figure to be true.' },
  { title: 'Students', body: 'A few cents a part decides whether you build one prototype or three.' },
  { title: 'A dead BOM line', body: 'Something went out of stock mid-project and you need a swap you can justify.' },
]

const FUTURE = [
  { title: 'BOM bulk upload', body: 'Paste a whole bill of materials and price the entire board in one pass instead of a line at a time.' },
  { title: 'Price history', body: 'The nightly recorder is already writing the series. The charts that read it are what is still missing.' },
  { title: 'Browse by category', body: 'Arrive without a part number and narrow down by package and rating instead.' },
  { title: 'Biggest savings this week', body: 'A public list of the swaps currently worth the most, so you can find one without searching first.' },
]

// Deliberately rounded and clearly badged. Real enough to show the shape of an
// answer, never presented as one.
const EXAMPLE_OFFERS = [
  { distributor: 'LCSC', sku: 'C41431778', stock: '38,000', price: '$0.0495', best: true },
  { distributor: 'Mouser', sku: '595-NE555DR', stock: '12,400', price: '$0.1120' },
]

const heading = {
  fontFamily: ARCHIVO, fontWeight: 900, fontSize: 14, color: C.orange,
  letterSpacing: '0.06em',
}

const lead = {
  fontSize: 17, color: '#2a2822', fontWeight: 500, lineHeight: 1.6,
  maxWidth: 700, margin: '14px 0 0',
}

function Section({ title, children, lead: leadText }) {
  return (
    <div style={{ borderTop: `3px solid ${C.ink}`, paddingTop: 26 }}>
      <div style={heading}>{title}</div>
      {leadText ? <p style={lead}>{leadText}</p> : null}
      {children}
    </div>
  )
}

export default function Landing() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 30 }}>
      <Section title="WHY PARTSOURCER">
        <p style={lead}>
          Finding a part that&apos;s <b>actually in stock</b>, at a fair price, with a footprint you can drop onto
          your board means tab-hopping across distributor sites for every line of your BOM. PartSourcer collapses
          that into one search, and points you to a cheaper equivalent when one genuinely exists.
        </p>
      </Section>

      {/* auto-fit rather than three fixed columns: a grid track never shrinks
          below its content, so on a phone three of them overflowed the page.
          This drops to two columns, then one, as the room runs out. */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16 }}>
        {STEPS.map((s) => (
          <div key={s.n} style={{ border: `3px solid ${C.ink}`, padding: 20,
            background: s.accent ? C.yellow : C.paper }}>
            <div style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 32, color: s.accent ? C.ink : C.orange }}>{s.n}</div>
            <div style={{ fontWeight: 700, fontSize: 16, marginTop: 10 }}>{s.title}</div>
            <div style={{ fontSize: 13, fontWeight: 500, marginTop: 6, color: s.accent ? '#3a3200' : C.sub }}>{s.body}</div>
          </div>
        ))}
      </div>

      <div style={{ border: `3px solid ${C.ink}`, background: C.ink, color: C.bg, padding: 26 }}>
        <div style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 14, color: C.yellow }}>
          EQUIVALENT OR NOTHING: THE LINE NEVER BLURS
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 22, marginTop: 16 }}>
          <div>
            <div style={{ fontWeight: 700, fontSize: 16, color: '#38d17a' }}>✓ Equivalent</div>
            <div style={{ fontSize: 14, fontWeight: 500, color: '#e6e2d4', marginTop: 6 }}>
              Same package, matching core specs, well stocked, and confirmed cheaper on a second reading of both prices. Safe to swap.
            </div>
          </div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 16, color: '#ffb02e' }}>✗ No match</div>
            <div style={{ fontSize: 14, fontWeight: 500, color: '#e6e2d4', marginTop: 6 }}>
              Close is not good enough. If a drop-in cannot be verified you get a plain no and the reason why, never a maybe.
            </div>
          </div>
        </div>
      </div>

      <Section
        title="THE RULES THIS RUNS ON"
        lead="Four promises that cost the product something. Each one means fewer results, more blank fields, or more honest refusals than a tool that simply guessed.">
        {/* 400px so four cards land as two rows of two. At 260px the third
            row fitted three and left the fourth stranded on its own. The
            min() caps the track at the container instead of that 400px
            floor, which is what stopped a 375px phone scrolling sideways. */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(400px, 100%), 1fr))',
          gap: 16, marginTop: 18 }}>
          {PRINCIPLES.map((p) => (
            <div key={p.title} style={{ border: `3px solid ${C.ink}`, background: C.paper, padding: 20 }}>
              <div style={{ fontWeight: 700, fontSize: 16 }}>{p.title}</div>
              <div style={{ fontSize: 13.5, color: C.sub, fontWeight: 500, marginTop: 8, lineHeight: 1.6 }}>{p.body}</div>
            </div>
          ))}
        </div>
      </Section>

      <Section
        title="WHAT AN ANSWER LOOKS LIKE"
        lead="Search a part and you get every distributor that stocks it side by side, the cheapest one marked, and the time each number was read.">
        <div data-testid="worked-example" style={{ border: `3px solid ${C.ink}`, background: C.paper,
          marginTop: 18 }}>
          <div style={{ background: C.yellow, borderBottom: `3px solid ${C.ink}`, padding: '10px 18px',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
            <span style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 13 }}>
              EXAMPLE ONLY, NOT LIVE DATA
            </span>
            <span style={{ fontSize: 12, fontWeight: 600, color: '#3a3200' }}>
              Search a real part to see current numbers
            </span>
          </div>
          <div style={{ padding: 20 }}>
            <div style={{ fontFamily: MONO, fontSize: 18, fontWeight: 600 }}>NE555DR</div>
            <div style={{ fontSize: 13, color: C.sub, fontWeight: 500, marginTop: 4 }}>
              Texas Instruments · SOIC-8 · single precision timer
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 16 }}>
              {EXAMPLE_OFFERS.map((o) => (
                <div key={o.distributor} style={{ display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(110px, 1fr))', gap: 8,
                  border: `2px solid ${o.best ? C.ink : '#ddd9c8'}`,
                  background: o.best ? C.yellow : C.bg, padding: '10px 14px', alignItems: 'baseline' }}>
                  <span style={{ fontWeight: 700, fontSize: 14 }}>{o.distributor}</span>
                  <span style={{ fontFamily: MONO, fontSize: 12, color: C.sub }}>{o.sku}</span>
                  <span style={{ fontSize: 13, fontWeight: 600 }}>{o.stock} in stock</span>
                  <span style={{ fontFamily: MONO, fontSize: 14, fontWeight: 700 }}>{o.price}</span>
                </div>
              ))}
            </div>
            <div style={{ fontSize: 13, color: C.sub, fontWeight: 500, marginTop: 14, lineHeight: 1.6 }}>
              A timer is not a resistor or a capacitor, so this one would come back with{' '}
              <b>no verified drop-in</b> and the reason why. That is the honest answer, not a missing feature.
            </div>
          </div>
        </div>
      </Section>

      <Section
        title="WHO IT'S FOR"
        lead="Built for people buying in ones and tens, not for anyone with a procurement team and a contract price.">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: 16, marginTop: 18 }}>
          {AUDIENCE.map((a) => (
            <div key={a.title} style={{ borderLeft: `3px solid ${C.orange}`, paddingLeft: 16 }}>
              <div style={{ fontWeight: 700, fontSize: 16 }}>{a.title}</div>
              <div style={{ fontSize: 13.5, color: C.sub, fontWeight: 500, marginTop: 6, lineHeight: 1.6 }}>{a.body}</div>
            </div>
          ))}
        </div>
      </Section>

      <Section
        title="FUTURE PLANS"
        lead="What is being built next. None of it is on the site yet, so none of it is described as though it were.">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
          gap: 16, marginTop: 18 }}>
          {FUTURE.map((f) => (
            <div key={f.title} style={{ border: `2px dashed ${C.ink}`, background: C.paper, padding: 18 }}>
              <div style={{ fontFamily: MONO, fontSize: 14, fontWeight: 600 }}>{f.title}</div>
              <div style={{ fontSize: 13, color: C.sub, fontWeight: 500, marginTop: 8, lineHeight: 1.6 }}>{f.body}</div>
            </div>
          ))}
        </div>
      </Section>

      <div style={{ border: `3px solid ${C.ink}`, background: C.yellow, padding: 26,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        flexWrap: 'wrap', gap: 16 }}>
        <div>
          <div style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 22, letterSpacing: '-0.02em' }}>
            SOMETHING LOOK WRONG?
          </div>
          <div style={{ fontSize: 14, fontWeight: 500, color: '#3a3200', marginTop: 6, maxWidth: 540 }}>
            Bad data, a part that should have matched, or a feature that would save you time. It is a solo
            project and every message gets read.
          </div>
        </div>
        <Link to="/contact" style={{ background: C.ink, color: C.yellow, fontFamily: ARCHIVO,
          fontWeight: 900, fontSize: 15, padding: '14px 24px', whiteSpace: 'nowrap' }}>
          GET IN TOUCH
        </Link>
      </div>
    </div>
  )
}
