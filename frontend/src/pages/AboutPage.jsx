import { Link } from 'react-router-dom'
import { C, ARCHIVO, MONO, PROSE_MAX } from '../theme.js'
import useDocumentTitle from '../useDocumentTitle.js'

const CARDS = [
  { title: 'FREE FOREVER', body: 'No paywall on core features. Any future revenue is optional affiliate links, never gating.' },
  { title: 'HONEST', body: "Every figure carries the moment it was read, and stock and price are never faked. If there's no valid equivalent, the page says so." },
  { title: 'FAST', body: 'Aggressive caching means search feels instant. Specs cache long; stock & price refresh often.' },
  { title: 'OPEN-SOURCE', body: 'MIT licensed. Fork it, self-host it, send a PR. Built for students, by a student.', accent: true },
]

const AUDIENCE = [
  {
    title: 'Hobbyists and makers',
    body: 'One-off boards where nobody is negotiating a contract price, and a part that says it is in stock needs to actually be in stock.',
  },
  {
    title: 'Students on a budget',
    body: 'A few cents per part is the difference between one prototype and three, and there is no procurement team to ask.',
  },
  {
    title: 'Anyone with a dead BOM line',
    body: 'A part went end-of-life or out of stock mid-project and you need a replacement you can actually justify swapping in.',
  },
]

const PROMISES = [
  {
    title: 'Never fake a number',
    body: 'Every stock and price figure carries the moment it was read, and the page shows it. If the upstream is down and the cache has gone stale, the API errors rather than quietly serving you an old number as though it were current.',
  },
  {
    title: 'Never overstate a match',
    body: 'Two parts are only called equivalent when the package and the core specs genuinely line up. Anything that cannot be verified comes back as an honest no with the reason, rather than a guess dressed up as a recommendation.',
  },
  {
    title: 'Never compare two prices measured differently',
    body: 'Distributors answer with different numbers depending on how you ask them. Candidates get ranked on parametric data first, then re-read on one single path before any saving is claimed, so both halves of a percentage come from the same place.',
  },
  {
    title: 'Never invent a price',
    body: 'A distributor that published no price hands back nothing, not zero. A zero would read as free and would win the cheapest comparison outright, so an unpriced offer is excluded from the claim and the page says so plainly.',
  },
]

const sectionTitle = {
  fontFamily: ARCHIVO, fontWeight: 900, fontSize: 14, color: C.orange,
  letterSpacing: '0.06em', marginTop: 46,
}

const body = { fontSize: 16, color: '#4a4838', lineHeight: 1.7, fontWeight: 500 }

export default function AboutPage() {
  useDocumentTitle('About')

  return (
    <section style={{ maxWidth: PROSE_MAX, margin: '0 auto', padding: '64px 28px 80px' }}>
      <span style={{ display: 'inline-block', background: C.orange, color: '#fff', fontWeight: 700,
        fontSize: 13, padding: '6px 12px' }}>ABOUT</span>
      <h1 style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 46, lineHeight: 1.0,
        letterSpacing: '-0.03em', margin: '22px 0 0' }}>
        A FREE TOOL FOR BUILDERS ON A BUDGET.
      </h1>
      <p style={{ ...body, fontSize: 18, margin: '20px 0 0' }}>
        Every hardware builder hits the same wall: finding a part that&apos;s actually in stock, at a good price,
        with a known footprint. Doing it by hand across distributor sites is slow and painful. PartSourcer does it
        in one search.
      </p>

      <div style={sectionTitle}>THE PROBLEM</div>
      <p style={{ ...body, margin: '14px 0 0' }}>
        Sourcing a board is not one hard question, it is fifty easy ones asked fifty times. For every line of a
        bill of materials you open the same handful of distributor sites, type the same part number, and compare
        numbers that are formatted differently, priced in different quantity breaks, and updated on different
        schedules. Half an hour later you have a spreadsheet nobody else can check.
      </p>
      <p style={{ ...body, margin: '14px 0 0' }}>
        The expensive part is not the search. It is that the answer goes stale the moment you write it down, and
        that a part which looked available on Tuesday can be gone on Thursday with nothing in your notes to tell
        you which it was. PartSourcer collapses that loop into one query and stamps every figure with the time it
        was read, so the answer carries its own expiry date.
      </p>

      <div style={sectionTitle}>WHO IT&apos;S FOR</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 14 }}>
        {AUDIENCE.map((item) => (
          <div key={item.title} style={{ borderLeft: `3px solid ${C.orange}`, paddingLeft: 16 }}>
            <div style={{ fontWeight: 700, fontSize: 16 }}>{item.title}</div>
            <div style={{ fontSize: 14, color: C.sub, fontWeight: 500, marginTop: 4,
              lineHeight: 1.6 }}>{item.body}</div>
          </div>
        ))}
      </div>
      <p style={{ ...body, fontSize: 15, margin: '18px 0 0' }}>
        If you buy reels at contract prices with a procurement team behind you, this is not built for you and
        will not beat what you already have.
      </p>

      <div style={sectionTitle}>WHAT IT PROMISES</div>
      <p style={{ ...body, margin: '14px 0 0' }}>
        A tool that compares prices is only worth anything if you can trust the comparison. These four rules are
        load-bearing rather than marketing, and each one costs the product something: fewer results, more blank
        fields, more honest refusals.
      </p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14, marginTop: 18 }}>
        {PROMISES.map((item) => (
          <div key={item.title} style={{ border: `3px solid ${C.ink}`, background: C.paper, padding: 20 }}>
            <div style={{ fontWeight: 700, fontSize: 16 }}>{item.title}</div>
            <div style={{ fontSize: 14, color: C.sub, fontWeight: 500, marginTop: 8,
              lineHeight: 1.6 }}>{item.body}</div>
          </div>
        ))}
      </div>

      <div style={sectionTitle}>WHAT IT IS TODAY</div>
      <p style={{ ...body, margin: '14px 0 0' }}>
        The cheaper-equivalent matcher covers resistors and capacitors, because those are the parts the upstream
        catalogue gives real parametric specs for. Ask it about a microcontroller and it will tell you it cannot
        verify a drop-in, which is the correct answer rather than a missing feature. Some fields are simply
        absent from some distributors, and where that happens the page leaves the line out instead of printing a
        placeholder.
      </p>

      {/* Four of them, so ps-grid-4 steps four to two to one and never
          leaves OPEN-SOURCE stranded underneath on its own. */}
      <div className="ps-grid-4" style={{ marginTop: 30 }}>
        {CARDS.map((card) => (
          <div key={card.title} style={{ border: `3px solid ${C.ink}`, padding: 22,
            background: card.accent ? C.yellow : C.paper }}>
            <div style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 20 }}>{card.title}</div>
            <div style={{ fontSize: 14, fontWeight: 500, marginTop: 8,
              color: card.accent ? '#3a3200' : C.sub }}>{card.body}</div>
          </div>
        ))}
      </div>

      {/* Moved here from "how it works". That page covers what the tool does
          for you; whose data it stands on belongs with what the project is. */}
      <div style={{ border: `3px solid ${C.ink}`, background: C.ink, color: '#fffdf5',
        padding: 22, marginTop: 30 }}>
        <div style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 14, color: C.yellow }}>
          WHERE THE DATA COMES FROM
        </div>
        <p style={{ fontSize: 14, color: '#e6e2d4', fontWeight: 500, lineHeight: 1.7, margin: '10px 0 0' }}>
          The LCSC side is built on the open{' '}
          <span style={{ fontFamily: MONO, color: C.yellow }}>jlcparts</span> /{' '}
          <span style={{ fontFamily: MONO, color: C.yellow }}>jlcsearch</span> ecosystem, a free parametric API
          over the LCSC and JLCPCB catalogue that syncs about once a day. Mouser and DigiKey answer in real time
          when credentials are configured. Specs and footprints cache long because they do not change; stock and
          price cache for hours. Every result shows the moment it was read, so you never have to guess which of
          those you are looking at.
        </p>
      </div>

      <div style={{ marginTop: 34, fontSize: 15, fontWeight: 500, color: C.sub }}>
        Something looks wrong, or you want to help?{' '}
        <Link to="/contact" style={{ color: C.orange, fontWeight: 700 }}>Get in touch</Link>.
      </div>
    </section>
  )
}
