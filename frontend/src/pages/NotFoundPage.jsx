import { useNavigate } from 'react-router-dom'
import { C } from '../theme.js'

const ARCHIVO = "'Archivo',sans-serif"

export default function NotFoundPage() {
  const navigate = useNavigate()

  return (
    <section style={{ maxWidth: 820, margin: '0 auto', padding: '90px 28px', textAlign: 'center' }}>
      <div style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 140, lineHeight: 1, color: C.orange }}>404</div>
      <div style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 30, marginTop: 8 }}>
        THIS PART ISN&apos;T ON THE BOARD.
      </div>
      <p style={{ fontSize: 16, color: C.sub, fontWeight: 500, marginTop: 12 }}>
        The page you&apos;re after doesn&apos;t exist. Let&apos;s get you back to searching.
      </p>
      <button type="button" onClick={() => navigate('/')} style={{ display: 'inline-block', marginTop: 22,
        cursor: 'pointer', background: C.ink, color: C.yellow, fontFamily: ARCHIVO, fontWeight: 900, fontSize: 15,
        padding: '14px 26px', border: `3px solid ${C.ink}`, boxShadow: `6px 6px 0 ${C.orange}` }}>
        ← BACK TO SEARCH
      </button>
    </section>
  )
}
