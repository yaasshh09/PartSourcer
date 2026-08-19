import { C, ARCHIVO } from '../theme.js'

const QA = [
  { q: 'Is it really free?', a: "Yes. Free forever on core features, no signup to search. It's MIT open-source, fork it if you like." },
  { q: 'How fresh is the stock data?', a: 'Specs and footprints are cached long, they don\'t change. We re-read stock and price every few hours, but the LCSC numbers come from an open database that itself syncs about once a day, and that is the real limit, not our cache. Mouser and DigiKey are live when they answer. Every result shows the time we read it.' },
  { q: 'Are you affiliated with LCSC or JLCPCB?', a: 'No. PartSourcer is an independent, community tool built on open data. Not affiliated with or endorsed by LCSC / JLCPCB.' },
  { q: 'How do I trust the "equivalent"?', a: 'We only call something an equivalent when the package and the core specs match, and we re-read both prices before claiming a saving. If we cannot verify a match we say none was found rather than guessing. Today that means resistors and capacitors, the parts the open database gives us real specs for.' },
]

export default function FaqPage() {
  return (
    <section style={{ maxWidth: 820, margin: '0 auto', padding: '64px 28px 80px' }}>
      <span style={{ display: 'inline-block', background: C.orange, color: '#fff', fontWeight: 700,
        fontSize: 13, padding: '6px 12px' }}>FAQ</span>
      <h1 style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 46, lineHeight: 1.0,
        letterSpacing: '-0.03em', margin: '22px 0 0' }}>
        QUICK ANSWERS.
      </h1>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginTop: 30 }}>
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
