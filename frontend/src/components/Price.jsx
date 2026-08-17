import { C, ARCHIVO, fmtPrice, NO_PRICE } from '../theme.js'

/**
 * A price, or a named gap where one would be.
 *
 * Renders bare text when there is a price, so the caller's own type styling
 * carries it exactly as before. When there is none it swaps in a small muted
 * label rather than inheriting the big bold treatment, because "no price" set
 * at 44px reads like a price.
 */
export default function Price({ value, size = 13 }) {
  if (value != null) return <>{fmtPrice(value)}</>
  return (
    <span style={{ fontFamily: ARCHIVO, fontWeight: 700, fontSize: size,
      color: C.muted, letterSpacing: 0 }}>
      {NO_PRICE}
    </span>
  )
}
