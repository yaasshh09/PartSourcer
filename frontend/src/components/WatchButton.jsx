import { useState } from 'react'
import { Link } from 'react-router-dom'
import { loadWatch, saveWatch, toggleWatch } from '../watch.js'
import { C, ARCHIVO } from '../theme.js'

export default function WatchButton({ part }) {
  const [list, setList] = useState(loadWatch)
  const watching = list.some((e) => e.k === part.mpn_key)

  function toggle() {
    // Read again rather than trusting state: another tab may have changed it.
    const next = toggleWatch(loadWatch(), part)
    saveWatch(next)
    setList(next)
  }

  return (
    <>
      <button type="button" aria-pressed={watching} onClick={toggle} className="ps-chip"
        style={{ cursor: 'pointer', fontFamily: ARCHIVO, fontWeight: 900, fontSize: 12,
          padding: '6px 10px', border: `2px solid ${C.ink}`, whiteSpace: 'nowrap',
          background: watching ? C.ink : C.paper, color: watching ? C.yellow : C.ink }}>
        {watching ? '★ Watching' : '☆ Watch'}
      </button>
      {watching ? (
        <Link to="/watchlist" style={{ fontSize: 12, fontWeight: 700, textDecoration: 'underline' }}>Watchlist</Link>
      ) : null}
    </>
  )
}
