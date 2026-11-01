import { useEffect, useState } from 'react'
import { getReadiness } from '../lib/api/client'
import type { Readiness } from '../lib/api/types'

/**
 * Whether the project's description is enough to draft a brief, asked again
 * each time the messages change. The rule lives in the backend
 * (app/policy/idea_readiness.py), so the button and the backend always agree.
 * Null while the first answer is on its way.
 */
export function useReadiness(projectId: string | null, messageCount: number): Readiness | null {
  const [readiness, setReadiness] = useState<Readiness | null>(null)
  useEffect(() => {
    if (!projectId) return
    let cancelled = false
    getReadiness(projectId)
      .then((value) => {
        if (!cancelled) setReadiness(value)
      })
      .catch(() => {
        // The backend could not be asked: do not lock the button; the backend
        // still refuses a start that is not ready, and says why.
        if (!cancelled) setReadiness({ ready: true, reason: null })
      })
    return () => {
      cancelled = true
    }
  }, [projectId, messageCount])
  return readiness
}
