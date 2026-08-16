import { C, ARCHIVO } from '../theme.js'

/**
 * The shell every "we could not answer that" surface shares: a dashed border,
 * a headline, and one line saying why. One component so the five of them
 * cannot drift apart, which matters because these are the screens that admit
 * a gap, and a gap admitted five slightly different ways reads as five
 * different severities.
 *
 * page is the whole-view version, for when nothing else loaded. inline sits
 * under content that did load, so it stays left aligned and quieter.
 */
export default function NoticePanel({ title, variant = 'page', children }) {
  const isPage = variant === 'page'
  return (
    <div style={{
      border: `3px dashed ${C.ink}`, background: C.paper,
      ...(isPage ? { padding: '56px 28px', textAlign: 'center' }
        : { padding: 28, marginTop: 24 }),
    }}>
      <div style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: isPage ? 30 : 16 }}>
        {title}
      </div>
      <div style={{
        fontWeight: 500, marginTop: 10,
        ...(isPage ? { fontSize: 15, color: C.sub }
          : { fontSize: 14, color: '#4a4838', maxWidth: 560 }),
      }}>
        {children}
      </div>
    </div>
  )
}
