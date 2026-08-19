import { useEffect, useState } from 'react'

/** How long a wait has to run before it is worth explaining. */
export const WAKE_NOTICE_AFTER_MS = 5000

export const WAKE_NOTICE =
  'Still going. The backend runs on a free plan and sleeps when nobody is '
  + 'using it, so the first request after a quiet spell spends 20 to 30 '
  + 'seconds waking it up. After that it is quick.'

/**
 * True once a load has been running long enough to look broken.
 *
 * The backend is on Render's free plan, which spins the container down when
 * it is idle, so the first request after a quiet spell really does take 20 to
 * 30 seconds. A skeleton on its own reads as a dead site for that long, and
 * this is the first thing most visitors see. Saying what is happening costs
 * nothing and is true.
 */
export function useWaking(loading) {
  const [waking, setWaking] = useState(false)

  useEffect(() => {
    if (!loading) {
      setWaking(false)
      return undefined
    }
    const timer = setTimeout(() => setWaking(true), WAKE_NOTICE_AFTER_MS)
    return () => clearTimeout(timer)
  }, [loading])

  return waking
}
