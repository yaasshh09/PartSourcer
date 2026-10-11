import { Link, useLocation } from 'react-router-dom'
import { useCompare, compareHref } from '../compare.jsx'
import { C, ARCHIVO, MONO, SHELL_MAX } from '../theme.js'

/**
 * Sticky to the bottom of the viewport as the last child of the page, so it
 * floats over content while scrolling and settles below the footer at the
 * end, without a spacer or a covered footer.
 */
export default function CompareTray() {
  const compare = useCompare()
  const { pathname } = useLocation()
  if (!compare || compare.keys.length === 0 || pathname === '/compare') return null
  const ready = compare.keys.length >= 2
  return (
    <aside aria-label="Compare tray" className="ps-tray" style={{ position: 'sticky', bottom: 0, zIndex: 30,
      background: C.ink, color: '#fff', borderTop: `3px solid ${C.yellow}` }}>
      <div style={{ maxWidth: SHELL_MAX, margin: '0 auto', padding: '10px 28px', display: 'flex',
        flexWrap: 'wrap', alignItems: 'center', gap: '8px 12px' }}>
        <span style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 13, color: C.yellow }}>COMPARE</span>
        <ul style={{ display: 'flex', flexWrap: 'wrap', gap: 8, listStyle: 'none', margin: 0,
          padding: 0, flex: '1 1 200px', minWidth: 0 }}>
          {compare.keys.map((k) => (
            <li key={k} style={{ display: 'flex', alignItems: 'center', gap: 6, maxWidth: '100%',
              border: '2px solid #555', padding: '3px 8px', fontFamily: MONO, fontSize: 12 }}>
              <span style={{ overflowWrap: 'anywhere' }}>{k}</span>
              <button type="button" aria-label={`Remove ${k} from compare`} onClick={() => compare.remove(k)} className="ps-chip"
                style={{ background: 'transparent', border: 'none', color: '#fff', cursor: 'pointer',
                  fontSize: 13, padding: 0 }}>✕</button>
            </li>
          ))}
        </ul>
        <button type="button" onClick={compare.clear} className="ps-chip" style={{ background: 'transparent', color: '#fff',
          border: '2px solid #777', fontWeight: 700, fontSize: 12, padding: '6px 10px', cursor: 'pointer' }}>
          Clear
        </button>
        {ready ? (
          <Link to={compareHref(compare.keys)} className="ps-press" style={{ background: C.orange, color: '#fff',
            fontFamily: ARCHIVO, fontWeight: 900, fontSize: 14, padding: '8px 16px',
            border: `2px solid ${C.yellow}` }}>{`Compare (${compare.keys.length})`}</Link>
        ) : (
          <span style={{ fontSize: 12, color: '#bbb', fontWeight: 600 }}>Pin one more to compare</span>
        )}
      </div>
    </aside>
  )
}
