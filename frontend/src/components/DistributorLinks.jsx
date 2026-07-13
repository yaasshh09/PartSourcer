import { C } from '../theme.js'

const ARCHIVO = "'Archivo',sans-serif"

export function lcscUrl(code) {
  return `https://www.lcsc.com/search?q=${encodeURIComponent(code)}`
}

export function jlcpcbUrl(code) {
  return `https://jlcpcb.com/parts/componentSearch?searchTxt=${encodeURIComponent(code)}`
}

export default function DistributorLinks({ code, variant = 'default' }) {
  const onYellow = variant === 'onYellow'
  const style = {
    fontFamily: ARCHIVO, fontWeight: 900, fontSize: 12, textDecoration: 'none',
    padding: '7px 12px', border: `2px solid ${onYellow ? '#5a4d1a' : C.ink}`,
    color: onYellow ? '#3a3200' : C.ink, background: 'transparent',
  }
  return (
    <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
      <a href={lcscUrl(code)} target="_blank" rel="noopener noreferrer" style={style}>
        View on LCSC ↗
      </a>
      <a href={jlcpcbUrl(code)} target="_blank" rel="noopener noreferrer" style={style}>
        View on JLCPCB ↗
      </a>
    </div>
  )
}
