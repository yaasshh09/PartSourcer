import { C, ARCHIVO, MONO, PROSE_MAX } from '../theme.js'
import CopyButton from '../components/CopyButton.jsx'
import useDocumentTitle from '../useDocumentTitle.js'

// Only routes a script can usefully call. The recorder's internal endpoint is
// left out on purpose: it takes a secret and is not for the public.
export const ENDPOINTS = [
  { path: '/api/search?q=STM32F103', what: 'Search every distributor. Results are merged by part number, 20 a page (page=2 and on).' },
  { path: '/api/part/STM32F103C8T6', what: 'One part with every offer, its stock, price breaks and when each was read. A legacy C code redirects to the part.' },
  { path: '/api/equivalent/0402WGJ0103TCE', what: 'A verified cheaper in-stock drop-in for a resistor or capacitor, or a null with the reason.' },
  { path: '/api/browse', what: 'The categories that can be browsed by value and package, and their filters.' },
  { path: '/api/browse/resistors?resistance=10k&package=0402', what: 'Parts in a category matching typed values. No prices: open the part for those.' },
  { path: '/api/history/STM32F103C8T6?days=90', what: 'Nightly LCSC price and stock readings, oldest first. recording: false means this site keeps none.' },
  { path: '/api/trends?keys=STM32F103C8T6&keys=NE555DR', what: 'Week-on-week LCSC price and stock change for up to 50 parts.' },
  { path: '/api/badge/STM32F103C8T6', what: 'An SVG stock badge for a README.' },
  { path: '/api/og/part/STM32F103C8T6', what: 'A 1200 by 630 PNG preview card with the price, stock and when they were read.' },
  { path: '/api/share/part/STM32F103C8T6', what: 'A link to paste in chat: it shows that card as the preview and opens the part page.' },
  { path: '/api/suggest?q=stm32', what: 'Part numbers opened here that start with what was typed.' },
  { path: '/api/fx', what: 'The ECB reference rates the site uses to show prices in EUR, GBP and INR.' },
  { path: '/api/status', what: 'How each distributor answered real requests over the past day.' },
]

const RULES = [
  'No key and no account. Each address gets 60 requests a minute, and a 429 carries Retry-After in seconds.',
  'Every offer carries an as_of saying when it was read. LCSC numbers come from a jlcparts snapshot that syncs about once a day, so they are not live. Mouser and DigiKey answer in real time.',
  'A price a distributor did not publish is null, never 0. Treat null as unknown.',
  'One distributor failing is still a 200, reported in sources. Only every source failing is a 502 or 504.',
  'Errors are {"detail": "..."} with a plain sentence. A 404 means every source answered and none has the part.',
  'Browsers on other sites are blocked by CORS. Call it from a script or a server.',
]

const box = { border: `3px solid ${C.ink}`, background: C.paper, padding: 22, marginBottom: 16 }

export default function DevelopersPage() {
  useDocumentTitle('API')
  const origin = typeof window !== 'undefined' ? window.location.origin : ''

  return (
    <section style={{ maxWidth: PROSE_MAX, margin: '0 auto', padding: '64px 28px 80px' }}>
      <span style={{ display: 'inline-block', background: C.ink, color: C.yellow, fontWeight: 700,
        fontSize: 13, padding: '6px 12px' }}>API</span>
      <h1 style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 46, lineHeight: 1.0,
        letterSpacing: '-0.03em', margin: '22px 0 30px' }}>
        SCRIPT AGAINST IT.
      </h1>
      <div style={box}>
        <h2 style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 18, margin: 0 }}>The rules</h2>
        <ul style={{ margin: '12px 0 0', paddingLeft: 20 }}>
          {RULES.map((r) => (
            <li key={r} style={{ fontSize: 15, fontWeight: 500, color: C.sub, marginTop: 6 }}>{r}</li>
          ))}
        </ul>
      </div>
      <div style={box}>
        <h2 style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 18, margin: 0 }}>Endpoints</h2>
        <ul style={{ listStyle: 'none', margin: '12px 0 0', padding: 0 }}>
          {ENDPOINTS.map((e) => (
            <li key={e.path} style={{ marginTop: 14 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                <code style={{ fontFamily: MONO, fontSize: 13, fontWeight: 600, overflowWrap: 'anywhere' }}>
                  {`GET ${e.path}`}
                </code>
                <CopyButton value={`curl "${origin}${e.path}"`} label={`Copy curl for ${e.path}`} />
              </div>
              <div style={{ fontSize: 14, fontWeight: 500, color: C.sub, marginTop: 4 }}>{e.what}</div>
            </li>
          ))}
        </ul>
      </div>
      <p style={{ fontSize: 14, color: C.sub, fontWeight: 500 }}>
        Full request and response shapes are in the backend README on GitHub, linked in the footer.
      </p>
    </section>
  )
}
