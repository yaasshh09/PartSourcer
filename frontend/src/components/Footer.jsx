import { Link } from 'react-router-dom'
import { C, ARCHIVO } from '../theme.js'
import { CONTACT } from '../contact.js'

const PRODUCT = [
  { label: 'Search', to: '/' },
  { label: 'About', to: '/about' },
  { label: 'How it works', to: '/how' },
  { label: 'FAQ', to: '/faq' },
  { label: 'Contact', to: '/contact' },
]

const PROJECT = [
  { label: 'GitHub', href: CONTACT.repoUrl },
  { label: 'MIT License', href: CONTACT.licenseUrl },
  { label: 'Report an issue', href: CONTACT.issuesUrl },
]

const REACH = [
  { label: CONTACT.email, href: `mailto:${CONTACT.email}` },
  { label: `Instagram ${CONTACT.instagram}`, href: CONTACT.instagramUrl, external: true },
]

const headingStyle = {
  fontFamily: ARCHIVO, fontWeight: 900, fontSize: 13, color: C.yellow,
  letterSpacing: '0.06em',
}

const listStyle = {
  display: 'flex', flexDirection: 'column', gap: 8, marginTop: 12,
  fontSize: 13, fontWeight: 500,
}

// Bright enough to read as a link on the dark panel. The old muted grey made
// every one of these look disabled.
const linkStyle = { color: '#e6e2d4' }

function Column({ title, children }) {
  return (
    <div>
      <div style={headingStyle}>{title}</div>
      <div style={listStyle}>{children}</div>
    </div>
  )
}

export default function Footer() {
  return (
    <footer style={{ background: C.ink, color: '#fffdf5', borderTop: `3px solid ${C.ink}` }}>
      <div style={{ maxWidth: 1120, margin: '0 auto', padding: '44px 28px 0' }}>
        {/* The blurb column is given more room than the link columns, and the
            whole thing collapses to a stack when there is no room for two. */}
        <div style={{ display: 'grid', gap: 32,
          gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))' }}>
          <div style={{ gridColumn: 'span 1', minWidth: 0 }}>
            <div style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 20, color: C.yellow }}>
              PARTSOURCER
            </div>
            <p style={{ fontSize: 13, color: '#bdb9aa', fontWeight: 500, lineHeight: 1.6,
              margin: '12px 0 0', maxWidth: 280 }}>
              Search a part once and see stock, price, footprint and datasheet across
              distributors, each stamped with when it was read. Free, open-source, no login.
            </p>
          </div>

          <Column title="PRODUCT">
            {PRODUCT.map((item) => (
              <Link key={item.label} to={item.to} style={linkStyle}>{item.label}</Link>
            ))}
          </Column>

          <Column title="PROJECT">
            {PROJECT.map((item) => (
              <a key={item.label} href={item.href} target="_blank" rel="noreferrer"
                style={linkStyle}>{item.label}</a>
            ))}
            <Link to="/nope" style={linkStyle}>404 demo</Link>
          </Column>

          <Column title="CONTACT">
            {REACH.map((item) => (
              <a key={item.label} href={item.href}
                {...(item.external ? { target: '_blank', rel: 'noreferrer' } : {})}
                style={{ ...linkStyle, wordBreak: 'break-word' }}>{item.label}</a>
            ))}
          </Column>
        </div>

        <div style={{ borderTop: `1px solid #3a382f`, marginTop: 34, padding: '18px 0 26px',
          display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10 }}>
          <div style={{ fontSize: 12, color: C.muted, fontWeight: 500 }}>
            Not affiliated with or endorsed by LCSC, JLCPCB, Mouser or DigiKey.
          </div>
          <div style={{ fontSize: 12, color: C.muted, fontWeight: 500 }}>
            MIT licensed. Built by{' '}
            <a href={CONTACT.githubUrl} target="_blank" rel="noreferrer"
              style={{ color: '#bdb9aa' }}>{CONTACT.github}</a>.
          </div>
        </div>
      </div>
    </footer>
  )
}
