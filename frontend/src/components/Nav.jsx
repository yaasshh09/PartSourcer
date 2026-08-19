import { NavLink, Link } from 'react-router-dom'
import { C, ARCHIVO } from '../theme.js'

const link = ({ isActive }) => ({
  cursor: 'pointer', padding: '6px 12px', fontWeight: 600, fontSize: 14,
  borderBottom: `3px solid ${isActive ? C.ink : 'transparent'}`,
  whiteSpace: 'nowrap', flex: '0 0 auto',
})

export default function Nav() {
  return (
    <header style={{ position: 'sticky', top: 0, zIndex: 20, background: C.yellow, borderBottom: `3px solid ${C.ink}` }}>
      {/* A wordmark plus five items is wider than a 375px phone. With a fixed
          height and no wrapping it used to push the whole document sideways,
          so every page scrolled horizontally on a phone. Nothing here is
          pinned to a width now: the links drop to their own row when they
          stop fitting beside the wordmark, and wrap again within that row,
          which costs vertical space on a phone but hides nothing. */}
      <div style={{ maxWidth: 1120, margin: '0 auto', padding: '8px 28px', minHeight: 66,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        flexWrap: 'wrap', rowGap: 4 }}>
        <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 26, height: 26, background: C.ink, display: 'flex', alignItems: 'center', justifyContent: 'center', flex: '0 0 auto' }}>
            <div style={{ width: 11, height: 11, background: C.orange }} />
          </div>
          <div style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 20, letterSpacing: '-0.03em', whiteSpace: 'nowrap' }}>PARTSOURCER</div>
        </Link>
        {/* 240px is about where the links stop being readable side by side,
            so that is the width at which they take a row of their own. They
            wrap rather than scroll: a scroll box pinned to flex-end hides the
            items at the start, which on a phone silently swallowed Search. */}
        <nav style={{ display: 'flex', alignItems: 'center', gap: 4, flex: '1 1 240px',
          justifyContent: 'flex-end', flexWrap: 'wrap', rowGap: 4 }}>
          <NavLink to="/" end style={link}>Search</NavLink>
          <NavLink to="/about" style={link}>About</NavLink>
          <NavLink to="/how" style={link}>How it works</NavLink>
          <NavLink to="/faq" style={link}>FAQ</NavLink>
          {/* The repo lives in the footer now. Everything up here moves you
              around the site, so the one item that left it stood out wrongly
              as the most emphasised thing in the header. */}
          <NavLink to="/contact" style={link}>Contact</NavLink>
        </nav>
      </div>
    </header>
  )
}
