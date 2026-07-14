import { NavLink, Link } from 'react-router-dom'
import { C } from '../theme.js'

const link = ({ isActive }) => ({
  cursor: 'pointer', padding: '6px 12px', fontWeight: 600, fontSize: 14,
  borderBottom: `3px solid ${isActive ? C.ink : 'transparent'}`,
})

export default function Nav() {
  return (
    <header style={{ position: 'sticky', top: 0, zIndex: 20, background: C.yellow, borderBottom: `3px solid ${C.ink}` }}>
      <div style={{ maxWidth: 1120, margin: '0 auto', padding: '0 28px', height: 66, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 26, height: 26, background: C.ink, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <div style={{ width: 11, height: 11, background: C.orange }} />
          </div>
          <div style={{ fontFamily: "'Archivo',sans-serif", fontWeight: 900, fontSize: 20, letterSpacing: '-0.03em' }}>PARTSOURCER</div>
        </Link>
        <nav style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <NavLink to="/" end style={link}>Search</NavLink>
          <NavLink to="/about" style={link}>About</NavLink>
          <NavLink to="/how" style={link}>How it works</NavLink>
          <NavLink to="/faq" style={link}>FAQ</NavLink>
          <a href="https://github.com/yaasshh09/PartSourcer" target="_blank" rel="noreferrer"
             style={{ marginLeft: 8, background: C.ink, color: C.yellow, fontWeight: 700, padding: '9px 14px' }}>GitHub</a>
        </nav>
      </div>
    </header>
  )
}
