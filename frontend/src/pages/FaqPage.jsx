import { C, ARCHIVO, PROSE_MAX } from '../theme.js'
import useDocumentTitle from '../useDocumentTitle.js'

const QA = [
  { q: 'Is it really free?', a: "Yes. Free forever on core features, no signup to search. It's MIT open-source, fork it if you like." },
  { q: 'How fresh is the stock data?', a: 'Specs and footprints are cached long, they don\'t change. Stock and price get re-read every few hours, but the LCSC numbers come from an open database that itself syncs about once a day, and that is the real limit, not the cache. Mouser and DigiKey are live when they answer. Every result shows the time it was read.' },
  { q: 'Are you affiliated with LCSC or JLCPCB?', a: 'No. PartSourcer is an independent, community tool built on open data. Not affiliated with or endorsed by LCSC / JLCPCB.' },
  { q: 'How do I trust the "equivalent"?', a: 'Something is only called an equivalent when the package and the core specs match, and both prices are re-read before a saving is claimed. If a match cannot be verified the answer is that none was found, rather than a guess. Today that means resistors and capacitors, the parts the open database carries real specs for.' },
]

export default function FaqPage() {
  useDocumentTitle('FAQ')

  return (
    <section style={{ maxWidth: PROSE_MAX, margin: '0 auto', padding: '64px 28px 80px' }}>
      <span style={{ display: 'inline-block', background: C.orange, color: '#fff', fontWeight: 700,
        fontSize: 13, padding: '6px 12px' }}>FAQ</span>
      <h1 style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 46, lineHeight: 1.0,
        letterSpacing: '-0.03em', margin: '22px 0 0' }}>
        QUICK ANSWERS.
      </h1>
      {/* Stacked, each answer ran the full width of the page and a 14px
          line crossed the whole monitor. A 560px floor lands the four as
          two rows of two when there is room and one column when there is
          not, so the width carries more answer rather than longer lines. */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(560px, 100%), 1fr))',
        gap: 16, marginTop: 30, alignItems: 'start' }}>
        {QA.map((item) => (
          <div key={item.q} style={{ border: `3px solid ${C.ink}`, background: C.paper, padding: 22 }}>
            <div style={{ fontWeight: 700, fontSize: 17 }}>{item.q}</div>
            <div style={{ fontSize: 14, color: C.sub, fontWeight: 500, marginTop: 8 }}>{item.a}</div>
          </div>
        ))}
      </div>
    </section>
  )
}
