import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { headlineOffer } from './offers.js'

export const MAX_COMPARE = 4
const STORAGE_KEY = 'ps-compare'

/** Non-empty strings of sane length, deduped, in order, at most four. */
export function cleanKeys(list) {
  const out = []
  for (const k of Array.isArray(list) ? list : []) {
    if (typeof k !== 'string' || !k || k.length > 200 || out.includes(k)) continue
    out.push(k)
    if (out.length === MAX_COMPARE) break
  }
  return out
}

// Repeated k params rather than one comma list: nothing stops an MPN
// containing a comma.
export function compareHref(keys) {
  return `/compare?${keys.map((k) => `k=${encodeURIComponent(k)}`).join('&')}`
}

// Storage can be blocked (private mode, strict settings) or hand-edited. Either
// way the tray starts empty instead of taking the page down.
function load() {
  try {
    return cleanKeys(JSON.parse(window.localStorage.getItem(STORAGE_KEY) || '[]'))
  } catch {
    return []
  }
}

function save(keys) {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(keys))
  } catch {
    // Persistence is a convenience. Losing it is fine.
  }
}

const CompareContext = createContext(null)

export function CompareProvider({ children }) {
  const [keys, setKeys] = useState(load)
  useEffect(() => { save(keys) }, [keys])

  const add = useCallback((k) => setKeys((ks) => cleanKeys([...ks, k])), [])
  const remove = useCallback((k) => setKeys((ks) => ks.filter((x) => x !== k)), [])
  const clear = useCallback(() => setKeys([]), [])
  const setAll = useCallback((list) => setKeys(cleanKeys(list)), [])

  const value = useMemo(() => ({
    keys, add, remove, clear, setAll,
    has: (k) => keys.includes(k),
    full: keys.length >= MAX_COMPARE,
  }), [keys, add, remove, clear, setAll])

  return <CompareContext.Provider value={value}>{children}</CompareContext.Provider>
}

/** null outside a provider, so a card rendered on its own simply has no pin. */
export function useCompare() {
  return useContext(CompareContext)
}

/**
 * Which columns lead each row. Facts about these parts only: they are not
 * equivalents, so there is no overall winner. A price counts when it is a
 * USD headline price; a mark needs at least two parts to compare.
 */
export function rowLeaders(parts) {
  const heads = parts.map((p) => (p ? headlineOffer(p) : null))

  const prices = heads.map((h) =>
    (h && h.currency === 'USD' && h.price_usd != null ? h.price_usd : null))
  const priced = prices.filter((v) => v != null)
  const lowestPrice = new Set()
  if (priced.length >= 2) {
    const min = Math.min(...priced)
    prices.forEach((v, i) => { if (v === min) lowestPrice.add(i) })
  }

  const stocks = parts.map((p, i) => (p ? (heads[i] ? heads[i].stock : 0) : null))
  const loaded = stocks.filter((v) => v != null)
  const mostStock = new Set()
  if (loaded.length >= 2) {
    const max = Math.max(...loaded)
    if (max > 0) stocks.forEach((v, i) => { if (v === max) mostStock.add(i) })
  }

  return { lowestPrice, mostStock }
}
