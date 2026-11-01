import { useCallback, useEffect, useState } from 'react'
import { completePrompt, getPlan } from '../lib/api/client'
import type { PlanSnapshot } from '../lib/api/types'

/**
 * The build plan a run has produced (roadmap, prompt pack, checks, links).
 *
 * It loads when the run changes, and again whenever `version` changes: the caller passes the number of plan events
 * seen so far, so the Plan step fills in while the plan is made, and a page reload simply loads what was saved.
 * Marking a prompt as done is saved on the backend, so it survives a reload too.
 */
export function usePlan(runId: string | null, version: number) {
  const [plan, setPlan] = useState<PlanSnapshot | null>(null)
  const [problem, setProblem] = useState<string | null>(null)

  useEffect(() => {
    if (runId === null) {
      setPlan(null)
      return
    }
    let cancelled = false
    getPlan(runId)
      .then((data) => {
        if (!cancelled) {
          setPlan(data)
          setProblem(null)
        }
      })
      .catch((error) => {
        if (!cancelled) setProblem(error instanceof Error ? error.message : 'The plan could not be loaded.')
      })
    return () => {
      cancelled = true
    }
  }, [runId, version])

  const markDone = useCallback(
    async (path: string, done: boolean) => {
      if (runId === null) return
      try {
        setPlan(await completePrompt(runId, path, done))
      } catch (error) {
        setProblem(error instanceof Error ? error.message : 'That could not be saved.')
      }
    },
    [runId],
  )

  return { plan, problem, markDone }
}
