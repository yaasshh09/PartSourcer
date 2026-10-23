import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { getFx } from './api.js'
import { setShownCurrency, C, fmtAsOf } from './theme.js'

export const CURRENCIES = ['USD', 'EUR', 'GBP', 'INR']
const STORAGE_KEY = 'ps-currency'

function stored() {
  try {
    const v = window.localStorage.getItem(STORAGE_KEY)
    return CURRENCIES.includes(v) ? v : 'USD'
  } catch {
    return 'USD'
  }
}

const CurrencyContext = createContext(null)

/**
 * Holds the display currency. App subscribes, so a change re-renders the
 * whole tree (without remounting it) and every formatter picks up the rate. Until rates arrive, and
 * whenever they cannot be had, prices stay in USD and the picker says why.
 */
export function CurrencyProvider({ children }) {
  const [state, setState] = useState({ code: 'USD', date: null, failed: false })

  const choose = useCallback((code) => {
    try { window.localStorage.setItem(STORAGE_KEY, code) } catch { /* convenience only */ }
    if (code === 'USD') {
      setShownCurrency('USD', 1)
      setState({ code: 'USD', date: null, failed: false })
      return
    }
    getFx().then((fx) => {
      const rate = fx.rates && fx.rates[code]
      if (!rate) throw new Error('no rate')
      setShownCurrency(code, rate)
      setState({ code, date: fx.date, failed: false })
    }).catch(() => {
      setShownCurrency('USD', 1)
      setState({ code: 'USD', date: null, failed: true })
    })
  }, [])

  useEffect(() => {
    const first = stored()
    if (first !== 'USD') choose(first)
  }, [choose])

  const value = useMemo(() => ({ ...state, choose }), [state, choose])
  return <CurrencyContext.Provider value={value}>{children}</CurrencyContext.Provider>
}

export function useCurrency() {
  return useContext(CurrencyContext)
}

export function CurrencySelect({ onDark = false }) {
  const cur = useCurrency()
  if (!cur) return null
  const note = cur.failed
    ? 'Rates are unavailable, so prices are in USD.'
    : cur.code !== 'USD' && cur.date
      ? `Converted from USD at the ECB rate of ${fmtAsOf(`${cur.date}T00:00:00Z`).split(' · ')[0]}. Distributors charge in USD.`
      : null
  return (
    <span style={{ display: 'inline-flex', flexWrap: 'wrap', alignItems: 'center', gap: 8, fontSize: 12, fontWeight: 600 }}>
      <select aria-label="Currency" value={cur.code} onChange={(e) => cur.choose(e.target.value)}
        style={{ fontWeight: 700, fontSize: 12, padding: '4px 6px', border: `2px solid ${onDark ? '#777' : C.ink}`,
          background: onDark ? C.ink : C.paper, color: onDark ? '#fff' : C.ink }}>
        {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
      </select>
      {note ? <span style={{ color: onDark ? '#bbb' : C.sub }}>{note}</span> : null}
    </span>
  )
}
