import { C, ARCHIVO, MONO, PROSE_MAX } from '../theme.js'
import useDocumentTitle from '../useDocumentTitle.js'

// Newest first. Each line is something a visitor can see or use, written from
// the commit that shipped it, so nothing here is a plan.
export const RELEASES = [
  { date: '2026-10-24', items: [
    'A watchlist keeps parts in this browser and shows how price and stock moved since you added them.',
    'Search results filter by in stock, package and distributor.',
    'Searches for 0.1uF, 100n or 100 nF find the 100nF parts LCSC lists.',
    'The search box suggests part numbers people have opened before.',
    'Part pages link to a KiCad library search and copy the easyeda2kicad command.',
    'A part a distributor calls obsolete or end of life is flagged, in the distributor\'s own words.',
    'Prices can be shown in EUR, GBP or INR at the dated ECB rate. Totals and exports stay in USD.',
    'A status page shows how each distributor answered over the past day.',
    'An API page lists every public endpoint and the rules for calling it.',
    'A command-line tool and a GitHub Action price a BOM outside the browser.',
    'A KiCad plugin opens the BOM check with the open board\'s parts filled in.',
    'A part can be shared as a link whose preview shows its price, stock and read time.',
    'On a phone the BOM check shows each line as a card instead of a wide table.',
    'Small grey and orange text is darker so it reads clearly, and inputs show keyboard focus.',
  ] },
  { date: '2026-10-23', items: [
    'A part page lists the other verified cheaper drop-ins under the main one.',
    'A part page can suggest a better-spec part that costs no more.',
    'A checked BOM downloads in the format JLCPCB assembly takes.',
    'The BOM check says what the whole list costs from one distributor.',
  ] },
  { date: '2026-10-14', items: [
    'Part pages chart recorded LCSC price and stock history.',
    'Search cards flag a weekly price drop or stock fall.',
    'An out-of-stock part says how long it usually takes to come back.',
  ] },
  { date: '2026-10-13', items: [
    'The BOM check finds cheaper drop-ins for its lines on request.',
    'Search can show only JLC Basic and Preferred parts.',
    'A part can carry a stock badge in a project README.',
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
