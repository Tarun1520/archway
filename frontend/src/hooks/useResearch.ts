import { useEffect, useState } from 'react'
import { getResearch } from '../lib/api/client'
import type { ResearchSnapshot } from '../lib/api/types'

/**
 * The research a run has produced so far.
 *
 * It loads when the run changes, and again whenever `version` changes. The
 * caller passes the number of research events seen so far (from the run's
 * live progress), so the Research tab fills in while the stage is working,
 * and a page reload simply loads what was saved.
 */
export function useResearch(runId: string | null, version: number) {
  const [research, setResearch] = useState<ResearchSnapshot | null>(null)
  const [problem, setProblem] = useState<string | null>(null)

  useEffect(() => {
    if (runId === null) {
      setResearch(null)
      return
    }
    let cancelled = false
    getResearch(runId)
      .then((data) => {
        if (!cancelled) {
          setResearch(data)
          setProblem(null)
        }
      })
      .catch((error) => {
        if (!cancelled) setProblem(error instanceof Error ? error.message : 'Research could not be loaded.')
      })
    return () => {
      cancelled = true
    }
  }, [runId, version])

  return { research, problem }
}
