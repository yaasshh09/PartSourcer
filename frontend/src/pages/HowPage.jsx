import { C } from '../theme.js'

const ARCHIVO = "'Archivo',sans-serif"
const MONO = "'IBM Plex Mono',monospace"

const STEPS = [
  { n: '01', title: 'You search', body: 'By MPN, LCSC code, or plain-text spec. We query an open parts database and return live stock, price, package and datasheet.' },
  { n: '02', title: 'We match a cheaper equivalent', body: 'Same footprint (hard requirement), matching key specs, in stock, and cheaper. Sorted by lowest price, tiebroken by stock. We return the best one.' },
  { n: '03', title: 'You save', body: 'See the % saved, the match reason, and swap with confidence. If we can\'t verify pin compatibility, we label it "similar part," not "equivalent."', accent: true },
]

export default function HowPage() {
  return (
    <section style={{ maxWidth: 820, margin: '0 auto', padding: '64px 28px 80px' }}>
      <span style={{ display: 'inline-block', background: C.ink, color: C.yellow, fontWeight: 700,
        fontSize: 13, padding: '6px 12px' }}>HOW IT WORKS</span>
      <h1 style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 46, lineHeight: 1.0,
        letterSpacing: '-0.03em', margin: '22px 0 0' }}>
        SEARCH → MATCH → SAVE.
      </h1>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginTop: 30 }}>
        {STEPS.map((step) => (
          <div key={step.n} style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: 20,
            border: `3px solid ${C.ink}`, padding: 22, background: step.accent ? C.yellow : C.paper,
            alignItems: 'start' }}>
            <div style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 40,
              color: step.accent ? C.ink : C.orange }}>{step.n}</div>
            <div>
              <div style={{ fontWeight: 700, fontSize: 16 }}>{step.title}</div>
              <div style={{ fontSize: 14, fontWeight: 500, marginTop: 6,
                color: step.accent ? '#3a3200' : C.sub }}>{step.body}</div>
            </div>
          </div>
        ))}
      </div>
      <div style={{ border: `3px solid ${C.ink}`, background: C.ink, color: '#fffdf5', padding: 22, marginTop: 24 }}>
        <div style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 14, color: C.yellow }}>
          WHERE THE DATA COMES FROM
        </div>
        <p style={{ fontSize: 14, color: '#e6e2d4', fontWeight: 500, lineHeight: 1.6, margin: '10px 0 0' }}>
          Built on the open <span style={{ fontFamily: MONO, color: C.yellow }}>jlcparts</span> / <span
            style={{ fontFamily: MONO, color: C.yellow }}>jlcsearch</span> ecosystem — a free, parametric API over
          the LCSC/JLCPCB catalog. Specs &amp; footprints cache long; stock &amp; price refresh in hours. Every
          result shows a &quot;data as of&quot; timestamp so you always know how fresh it is.
        </p>
      </div>
    </section>
  )
}
