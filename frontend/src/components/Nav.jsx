import { useState, useEffect } from 'react'
import { NavLink, Link, useLocation } from 'react-router-dom'
import { C, ARCHIVO, SHELL_MAX } from '../theme.js'

const link = ({ isActive }) => ({
  cursor: 'pointer', padding: '6px 12px', fontWeight: 600, fontSize: 14,
  borderBottom: `3px solid ${isActive ? C.ink : 'transparent'}`,
  whiteSpace: 'nowrap', flex: '0 0 auto',
})

const ITEMS = [
  { to: '/', label: 'Search', end: true },
  { to: '/about', label: 'About' },
  { to: '/how', label: 'How it works' },
  { to: '/faq', label: 'FAQ' },
  // The repo lives in the footer. Everything up here moves you around the
  // site, so the one item that left it stood out wrongly as the most
  // emphasised thing in the header.
  { to: '/contact', label: 'Contact' },
]

export default function Nav() {
  const [open, setOpen] = useState(false)
  const { pathname } = useLocation()

  // Following a link inside the panel changes the route without unmounting
  // the header, so the panel would otherwise stay open on top of the page
  // you just asked for.
  useEffect(() => { setOpen(false) }, [pathname])

  return (
    <header style={{ position: 'sticky', top: 0, zIndex: 20, background: C.yellow, borderBottom: `3px solid ${C.ink}` }}>
      {/* The wordmark plus five links needs about 390px of row. A 375px phone
          does not have it, and wrapping only moved the problem: the links
          took a second row and left Contact stranded alone on a third. Below
          640px they collapse behind the toggle instead. Between there and
          full width they still wrap, which costs a row but hides nothing. */}
      <div style={{ maxWidth: SHELL_MAX, margin: '0 auto', padding: '8px 28px', minHeight: 66,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        flexWrap: 'wrap', rowGap: 4 }}>
        <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 26, height: 26, background: C.ink, display: 'flex', alignItems: 'center', justifyContent: 'center', flex: '0 0 auto' }}>
            <div style={{ width: 11, height: 11, background: C.orange }} />
          </div>
          <div style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 20, letterSpacing: '-0.03em', whiteSpace: 'nowrap' }}>PARTSOURCER</div>
        </Link>

        {/* 44px square so it is a real thumb target rather than a glyph you
            have to aim at. */}
        <button type="button" className="ps-nav-toggle"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open} aria-controls="ps-nav-links"
          aria-label={open ? 'Close menu' : 'Open menu'}
          style={{ width: 44, height: 44, alignItems: 'center', justifyContent: 'center',
            background: 'transparent', border: `3px solid ${C.ink}`, fontSize: 18,
            lineHeight: 1, color: C.ink, padding: 0 }}>
          {open ? '✕' : '☰'}
        </button>

        <nav id="ps-nav-links" className="ps-nav-links" data-open={open ? 'true' : 'false'}>
          {ITEMS.map((item) => (
            <NavLink key={item.to} to={item.to} {...(item.end ? { end: true } : {})} style={link}>
              {item.label}
            </NavLink>
          ))}
        </nav>
      </div>
    </header>
  )
}
