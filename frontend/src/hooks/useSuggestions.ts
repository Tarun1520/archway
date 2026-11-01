import { useCallback, useEffect, useState } from 'react'
import { useModelThinking } from './useModelThinking'
import { getSuggestions } from '../lib/api/client'
import type { BriefSuggestions } from '../lib/api/types'

export type SuggestionsState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'ready'; data: BriefSuggestions }
  | { status: 'error'; message: string }

/**
 * AI suggestions for the draft brief being edited.
 *
 * It asks the backend once per brief version. The backend saves the answer, so
 * a reload, or opening the page twice, does not spend another model call. A
 * failure (for example a rate limit) is shown with a "Try again" button; the
 * brief can always be edited without suggestions.
 */
export function useSuggestions(runId: string | null, briefVersion: number, enabled: boolean) {
  const [state, setState] = useState<SuggestionsState>({ status: 'idle' })
  // The model is writing suggestions: the studio shows it is waiting.
  useModelThinking(state.status === 'loading')
  const [attempt, setAttempt] = useState(0)
  // True after the user pressed a retry button: ask the model again for generic-only questions.
  const [retryStandard, setRetryStandard] = useState(false)

  useEffect(() => {
    if (!enabled || runId === null) return
    let cancelled = false
    setState({ status: 'loading' })
    getSuggestions(runId, retryStandard)
      .then((data) => {
        if (!cancelled) setState({ status: 'ready', data })
      })
      .catch((error) => {
        if (!cancelled)
          setState({ status: 'error', message: error instanceof Error ? error.message : 'Suggestions are not available.' })
      })
    return () => {
      cancelled = true
    }
    // briefVersion is a dependency on purpose: a new version needs new suggestions.
  }, [runId, briefVersion, enabled, attempt])

  const retry = useCallback(() => {
    setRetryStandard(true)
    setAttempt((n) => n + 1)
  }, [])
  return { state, retry }
}
