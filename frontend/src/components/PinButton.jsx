import { useEffect } from 'react'
import { useCompare, MAX_COMPARE } from '../compare.jsx'
import { C, ARCHIVO } from '../theme.js'

// hotkey: the part page's own pin answers to c. Only one button on a page may
// take it, so cards in a list leave it off.
export default function PinButton({ mpnKey, hotkey = false }) {
  const compare = useCompare()
  const pinned = !!compare && compare.has(mpnKey)
  const blocked = !!compare && !pinned && compare.full

  useEffect(() => {
    if (!hotkey || !compare || !mpnKey) return undefined
    const onKey = (e) => {
      if (e.key !== 'c' || e.ctrlKey || e.metaKey || e.altKey) return
      const el = document.activeElement
      if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.isContentEditable)) return
      if (pinned) compare.remove(mpnKey)
      else if (!blocked) compare.add(mpnKey)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [hotkey, compare, mpnKey, pinned, blocked])

  if (!compare || !mpnKey) return null
  return (
    <button type="button" aria-pressed={pinned} disabled={blocked} className="ps-chip"
      aria-keyshortcuts={hotkey ? 'c' : undefined} title={hotkey ? 'Shortcut: c' : undefined}
      onClick={() => (pinned ? compare.remove(mpnKey) : compare.add(mpnKey))}
      style={{ cursor: blocked ? 'not-allowed' : 'pointer', fontFamily: ARCHIVO, fontWeight: 900,
        fontSize: 12, padding: '6px 10px', border: `2px solid ${C.ink}`, whiteSpace: 'nowrap',
        background: pinned ? C.ink : C.paper, color: pinned ? C.yellow : C.ink,
        opacity: blocked ? 0.5 : 1 }}>
      {pinned ? '✓ Comparing' : blocked ? `Tray full (${MAX_COMPARE})` : '+ Compare'}
    </button>
  )
}
