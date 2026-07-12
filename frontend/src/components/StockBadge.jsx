import { stockInfo } from '../theme.js'

export default function StockBadge({ stock }) {
  const s = stockInfo(stock)
  return (
    <span style={{ background: s.bg, color: s.color, padding: '3px 10px', fontSize: 12, fontWeight: 700 }}>
      {s.label}
    </span>
  )
}
