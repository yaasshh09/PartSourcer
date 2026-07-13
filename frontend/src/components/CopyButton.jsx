import { useState, useEffect, useRef } from 'react'
import { C } from '../theme.js'

const MONO = "'IBM Plex Mono',monospace"

export default function CopyButton({ value, label = 'Copy', variant = 'default' }) {
  const [copied, setCopied] = useState(false)
  const timer = useRef(null)

  useEffect(() => () => { if (timer.current) clearTimeout(timer.current) }, [])

  if (!navigator.clipboard || !navigator.clipboard.writeText) return null

  function copy() {
    navigator.clipboard.writeText(value).then(() => {
      setCopied(true)
      if (timer.current) clearTimeout(timer.current)
      timer.current = setTimeout(() => setCopied(false), 1400)
    }).catch(() => {})
  }

  const onYellow = variant === 'onYellow'
  return (
    <button type="button" onClick={copy} aria-label={label}
      style={{ cursor: 'pointer', fontFamily: MONO, fontSize: 12, lineHeight: 1,
        background: 'transparent', border: `2px solid ${onYellow ? '#5a4d1a' : '#d8d4c4'}`,
        color: onYellow ? '#5a4d1a' : C.sub, padding: '3px 7px' }}>
      {copied ? '✓' : '⧉'}
    </button>
  )
}
