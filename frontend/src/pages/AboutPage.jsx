import { C } from '../theme.js'

const ARCHIVO = "'Archivo',sans-serif"

const CARDS = [
  { title: 'FREE FOREVER', body: 'No paywall on core features. Any future revenue is optional affiliate links — never gating.' },
  { title: 'HONEST', body: "We show data freshness and never fake stock or price. If there's no valid equivalent, we say so." },
  { title: 'FAST', body: 'Aggressive caching means search feels instant. Specs cache long; stock & price refresh often.' },
  { title: 'OPEN-SOURCE', body: 'MIT licensed. Fork it, self-host it, send a PR. Built for students, by a student.', accent: true },
]

export default function AboutPage() {
  return (
    <section style={{ maxWidth: 820, margin: '0 auto', padding: '64px 28px 80px' }}>
      <span style={{ display: 'inline-block', background: C.orange, color: '#fff', fontWeight: 700,
        fontSize: 13, padding: '6px 12px' }}>ABOUT</span>
      <h1 style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 46, lineHeight: 1.0,
        letterSpacing: '-0.03em', margin: '22px 0 0' }}>
        A FREE TOOL FOR BUILDERS ON A BUDGET.
      </h1>
      <p style={{ fontSize: 18, color: '#4a4838', lineHeight: 1.6, fontWeight: 500, margin: '20px 0 0' }}>
        Every hardware builder hits the same wall: finding a part that&apos;s actually in stock, at a good price,
        with a known footprint. Doing it by hand across distributor sites is slow and painful. PartSourcer does it
        in one search.
      </p>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginTop: 30 }}>
        {CARDS.map((card) => (
          <div key={card.title} style={{ border: `3px solid ${C.ink}`, padding: 22,
            background: card.accent ? C.yellow : C.paper }}>
            <div style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 20 }}>{card.title}</div>
            <div style={{ fontSize: 14, fontWeight: 500, marginTop: 8,
              color: card.accent ? '#3a3200' : C.sub }}>{card.body}</div>
          </div>
        ))}
      </div>
    </section>
  )
}
