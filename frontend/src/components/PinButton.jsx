import { useCompare, MAX_COMPARE } from '../compare.jsx'
import { C, ARCHIVO } from '../theme.js'

export default function PinButton({ mpnKey }) {
  const compare = useCompare()
  if (!compare || !mpnKey) return null
  const pinned = compare.has(mpnKey)
  const blocked = !pinned && compare.full
  return (
    <button type="button" aria-pressed={pinned} disabled={blocked} className="ps-chip"
      onClick={() => (pinned ? compare.remove(mpnKey) : compare.add(mpnKey))}
      style={{ cursor: blocked ? 'not-allowed' : 'pointer', fontFamily: ARCHIVO, fontWeight: 900,
        fontSize: 12, padding: '6px 10px', border: `2px solid ${C.ink}`, whiteSpace: 'nowrap',
        background: pinned ? C.ink : C.paper, color: pinned ? C.yellow : C.ink,
        opacity: blocked ? 0.5 : 1 }}>
      {pinned ? '✓ Comparing' : blocked ? `Tray full (${MAX_COMPARE})` : '+ Compare'}
    </button>
  )
}
