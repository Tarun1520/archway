import { useEffect, useState } from 'react'
import { screenFromHash } from '../lib/hashRoute'
import type { Screen } from '../lib/hashRoute'

/**
 * Tells a component which screen the address bar is asking for, and updates
 * when the part after "#" changes (a link was clicked, or Back was pressed).
 */
export function useHashRoute(): Screen {
  const [screen, setScreen] = useState<Screen>(() => screenFromHash(window.location.hash))

  useEffect(() => {
    const onHashChange = () => setScreen(screenFromHash(window.location.hash))
    window.addEventListener('hashchange', onHashChange)
    // The function returned from an effect is the clean-up: stop listening.
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  return screen
}
