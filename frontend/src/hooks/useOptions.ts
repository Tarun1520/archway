import { useEffect, useState } from 'react'
import { getOptions } from '../lib/api/client'
import type { OptionsSnapshot } from '../lib/api/types'

/**
 * The architecture options a run has produced so far.
 *
 * It loads when the run changes, and again whenever `version` changes. The caller passes the number of
 * options events seen so far (from the run's live progress), so the Options step fills in while the
 * options are being drafted and reviewed, and a page reload simply loads what was saved.
 */
export function useOptions(runId: string | null, version: number) {
  const [options, setOptions] = useState<OptionsSnapshot | null>(null)
  const [problem, setProblem] = useState<string | null>(null)

  useEffect(() => {
    if (runId === null) {
      setOptions(null)
      return
    }
    let cancelled = false
    getOptions(runId)
      .then((data) => {
        if (!cancelled) {
          setOptions(data)
          setProblem(null)
        }
      })
      .catch((error) => {
        if (!cancelled) setProblem(error instanceof Error ? error.message : 'The options could not be loaded.')
      })
    return () => {
      cancelled = true
    }
  }, [runId, version])

  return { options, problem }
}
