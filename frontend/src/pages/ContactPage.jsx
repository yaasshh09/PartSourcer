import { C, ARCHIVO, MONO } from '../theme.js'
import { CONTACT } from '../contact.js'
import useDocumentTitle from '../useDocumentTitle.js'

const WAYS = [
  {
    label: 'EMAIL',
    value: CONTACT.email,
    href: `mailto:${CONTACT.email}`,
    body: 'Best for questions, ideas, or anything that needs a proper reply.',
  },
  {
    label: 'INSTAGRAM',
    value: CONTACT.instagram,
    href: CONTACT.instagramUrl,
    external: true,
    body: 'Quickest for a short message.',
  },
  {
    label: 'GITHUB',
    value: CONTACT.github,
    href: CONTACT.githubUrl,
    external: true,
    body: 'Code, forks, and pull requests. The whole project is here.',
    accent: true,
  },
]

export default function ContactPage() {
  useDocumentTitle('Contact')

  return (
    <section style={{ maxWidth: 820, margin: '0 auto', padding: '64px 28px 80px' }}>
      <span style={{ display: 'inline-block', background: C.orange, color: '#fff', fontWeight: 700,
        fontSize: 13, padding: '6px 12px' }}>CONTACT</span>
      <h1 style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 46, lineHeight: 1.0,
        letterSpacing: '-0.03em', margin: '22px 0 0' }}>
        GET IN TOUCH.
      </h1>
      <p style={{ fontSize: 18, color: '#4a4838', lineHeight: 1.6, fontWeight: 500, margin: '20px 0 0' }}>
        PartSourcer is a solo project, so there is no support desk here, just me. Whether a part
        looked wrong, a feature would help your workflow, or you want to contribute, say so and
        it gets read.
      </p>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
        gap: 16, marginTop: 30 }}>
        {WAYS.map((way) => (
          <a key={way.label} href={way.href}
            {...(way.external ? { target: '_blank', rel: 'noreferrer' } : {})}
            style={{ display: 'block', border: `3px solid ${C.ink}`, padding: 18,
              background: way.accent ? C.yellow : C.paper, color: C.ink }}>
            <div style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 14,
              color: way.accent ? C.ink : C.orange }}>{way.label}</div>
            {/* Mono so a handle or an address can be read character by
                character, which is what you do before typing one out. 13px
                because the address is 24 characters and at 14 it broke across
                two lines mid-word, which is the one string you cannot afford
                to garble. break-word stays as the fallback on a narrow phone,
                where wrapping beats overflowing. */}
            <div style={{ fontFamily: MONO, fontSize: 13, fontWeight: 600, marginTop: 8,
              wordBreak: 'break-word' }}>{way.value}</div>
            <div style={{ fontSize: 13, fontWeight: 500, marginTop: 8,
              color: way.accent ? '#3a3200' : C.sub }}>{way.body}</div>
          </a>
        ))}
      </div>

      {/* A bug in an email thread is a bug only two people can see. */}
      <div style={{ border: `3px solid ${C.ink}`, background: C.ink, color: '#fffdf5',
        padding: 22, marginTop: 24 }}>
        <div style={{ fontFamily: ARCHIVO, fontWeight: 900, fontSize: 14, color: C.yellow }}>
          FOUND A BUG OR SOME BAD DATA?
        </div>
        <p style={{ fontSize: 14, color: '#e6e2d4', fontWeight: 500, lineHeight: 1.6, margin: '10px 0 0' }}>
          Open a{' '}
          <a href={CONTACT.issuesUrl} target="_blank" rel="noreferrer"
            style={{ color: C.yellow, fontWeight: 700 }}>GitHub issue</a>{' '}
          rather than sending it here. It stays visible, anyone else hitting the same thing can
          find it, and the fix ends up attached to it. Paste the part number and what you expected
          to see, and it is usually enough to reproduce.
        </p>
      </div>
    </section>
  )
}
