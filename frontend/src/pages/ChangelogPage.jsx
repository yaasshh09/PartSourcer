import { C, ARCHIVO, MONO, PROSE_MAX } from '../theme.js'
import useDocumentTitle from '../useDocumentTitle.js'

// Newest first. Each line is something a visitor can see or use, written from
// the commit that shipped it, so nothing here is a plan.
export const RELEASES = [
  { date: '2026-10-13', items: [
    'The BOM check prices a list for any number of boards.',
    'A BOM line that would take most of a distributor\'s stock says so.',
    'KiCad, Altium and JLCPCB BOM exports load without editing.',
    'Searches that found parts show up again under the search box.',
    'A search that finds nothing offers a shorter retry and a way to browse.',
    'Part pages show the total stock across distributors.',
    'A part can be copied as a BOM line at the quantity you typed.',
    'Every offer has a link to report wrong stock or price.',
    'A part page starts loading when the pointer rests on its search card.',
  ] },
  { date: '2026-10-11', items: [
    'New BOM check: paste a parts list and every line is priced at its quantity.',
    'The BOM check reads spreadsheet exports, loads a CSV, and shares as a link.',
    'Part pages show each distributor\'s price breaks and the price at the quantity you need.',
    'Search results can be sorted by price, low to high.',
    'A compare page puts up to four pinned parts side by side.',
    'Prices say they leave out shipping, tax and import duties.',
  ] },
  { date: '2026-09-27', items: [
    'Browse resistors, capacitors, LEDs, diodes, MOSFETs and LDOs by value and package.',
    'Pin parts from search, browse or a part page to compare them.',
  ] },
  { date: '2026-08-20', items: [
    'A contact page, wider pages, and the page name in the browser tab.',
    'Security headers and rate limits on the API.',
  ] },
  { date: '2026-08-19', items: [
    'The backend runs next to its database, so cached pages load fast.',
    'A price no longer changes when you click from a search card to the part page.',
    'A slow first load explains itself instead of just spinning.',
  ] },
  { date: '2026-08-17', items: [
    'A distributor that publishes no price shows "no price", never $0.',
    'The manufacturer and datasheet show wherever a distributor supplies them.',
  ] },
]

export default function ChangelogPage() {
  useDocumentTitle('Changelog')

  return (
    <section style={{ maxWidth: PROSE_MAX, margin: '0 auto', padding: '64px 28px 80px' }}>
      <span style={{ display: 'inline-block', background: C.ink, color: C.yellow, fontWeight: 700,
        fontSize: 13, padding: '6px 12px' }}>CHANGELOG</span>
      <h1 style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 46, lineHeight: 1.0,
        letterSpacing: '-0.03em', margin: '22px 0 30px' }}>
        WHAT CHANGED.
      </h1>
      {RELEASES.map((r) => (
        <div key={r.date} style={{ border: `3px solid ${C.ink}`, background: C.paper, padding: 22,
          marginBottom: 16 }}>
          <h2 style={{ fontFamily: MONO, fontWeight: 600, fontSize: 15, margin: 0 }}>{r.date}</h2>
          <ul style={{ margin: '12px 0 0', paddingLeft: 20 }}>
            {r.items.map((item) => (
              <li key={item} style={{ fontSize: 15, fontWeight: 500, color: C.sub, marginTop: 6 }}>{item}</li>
            ))}
          </ul>
        </div>
      ))}
    </section>
  )
}
