import { useEffect, useState } from 'react'
import { getConfig } from '../lib/api/client'
import type { PublicConfig } from '../lib/api/types'

/**
 * The three states a piece of loaded data can be in. Naming them makes it
 * impossible to forget the "still loading" and "it failed" cases in the UI.
 */
export type Loadable<T> =
  | { state: 'loading' }
  | { state: 'ready'; value: T }
  | { state: 'unreachable'; reason: string }

/** Loads the backend's public configuration (modes, badge, call caps) once. */
export function useBackendConfig(): Loadable<PublicConfig> {
  const [config, setConfig] = useState<Loadable<PublicConfig>>({ state: 'loading' })

  useEffect(() => {
    // `cancelled` stops a late answer from updating a screen that has gone.
    let cancelled = false
    getConfig()
      .then((value) => {
        if (!cancelled) setConfig({ state: 'ready', value })
      })
      .catch((error: unknown) => {
        const reason = error instanceof Error ? error.message : 'unknown error'
        if (!cancelled) setConfig({ state: 'unreachable', reason })
      })
    return () => {
      cancelled = true
    }
  }, [])

  return config
}
