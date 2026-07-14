import { Link } from 'react-router-dom'
import { C } from '../theme.js'

export default function Footer() {
  return (
    <footer style={{ background: C.ink, color: '#fffdf5', borderTop: `3px solid ${C.ink}` }}>
      <div style={{ maxWidth: 1120, margin: '0 auto', padding: '26px 28px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap', fontSize: 13, fontWeight: 600 }}>
          <span style={{ fontFamily: "'Archivo',sans-serif", fontWeight: 900, fontSize: 16, color: C.yellow }}>PARTSOURCER</span>
          <a href="https://github.com/yaasshh09/PartSourcer" target="_blank" rel="noreferrer" style={{ color: '#fffdf5' }}>GitHub</a>
          <span style={{ color: C.muted }}>MIT License</span>
          <Link to="/nope" style={{ color: C.muted }}>404 demo</Link>
        </div>
        <div style={{ fontSize: 12, color: C.muted, fontWeight: 500 }}>Not affiliated with or endorsed by LCSC / JLCPCB.</div>
      </div>
    </footer>
  )
}
