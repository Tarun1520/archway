import { useCallback, useEffect, useRef, useState } from 'react'
import { getGithubLimits } from '../lib/api/client'
import type { GithubLimits } from '../lib/api/types'

/** How often GitHub's limits are re-read: quickly while research is working, slowly otherwise. */
const POLL_BUSY_MS = 5_000
const POLL_IDLE_MS = 30_000

export interface GithubLimitsState {
  /** The latest answer, or null before the first one (or if the backend is unreachable). */
  limits: GithubLimits | null
  /** True when the last attempt to read the limits failed (backend off, or GitHub unreachable). */
  failed: boolean
  /** When that answer arrived (ms since 1970), so countdowns can run from it. */
  receivedAt: number
  /** Now, ticking once a second, so countdowns redraw. */
  now: number
}

/**
 * Keeps GitHub's real allowance up to date for the limit bar.
 *
 * LEARNING NOTE (frontend, not in the learning guide): the numbers come from
 * the backend, which reads them from GitHub's free /rate_limit endpoint. The
 * countdown is counted in the browser between answers, and a fresh answer is
 * fetched the moment an empty meter reaches zero, so the bar refills on screen
 * as soon as GitHub does.
 */
export function useGithubLimits(busy: boolean): GithubLimitsState {
  const [limits, setLimits] = useState<GithubLimits | null>(null)
  const [failed, setFailed] = useState(false)
  const [receivedAt, setReceivedAt] = useState(() => Date.now())
  const [now, setNow] = useState(() => Date.now())
  const refilledFor = useRef<number | null>(null)

  const load = useCallback(() => {
    getGithubLimits()
      .then((answer) => {
        setLimits(answer)
        setFailed(false)
        setReceivedAt(Date.now())
      })
      .catch(() => {
        // Keep the last answer rather than inventing one, but say the read failed.
        setFailed(true)
      })
  }, [])

  // Poll.
  useEffect(() => {
    load()
    const id = window.setInterval(load, busy ? POLL_BUSY_MS : POLL_IDLE_MS)
    return () => window.clearInterval(id)
  }, [busy, load])

  // Tick once a second.
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(id)
  }, [])

  // When an empty meter's countdown ends, ask again at once.
  useEffect(() => {
    if (!limits?.available) return
    for (const meter of [limits.core, limits.search]) {
      if (!meter || meter.remaining > 0) continue
      const elapsed = (now - receivedAt) / 1000
      if (elapsed >= meter.seconds_until_reset && refilledFor.current !== receivedAt) {
        refilledFor.current = receivedAt
        load()
      }
    }
  }, [now, receivedAt, limits, load])

  return { limits, failed, receivedAt, now }
}
