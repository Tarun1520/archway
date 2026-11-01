import { createContext, useContext } from 'react'
import { STUDIO_HASH } from '../lib/hashRoute'

/**
 * Opens the workspace. Inside <SpaceTransition> it plays the space transition
 * first; anywhere else (tests, or if the transition is not mounted) it simply
 * changes the address.
 */
export const GoToWorkspaceContext = createContext<() => void>(() => {
  window.location.hash = STUDIO_HASH
})

/** The function that takes the person to the workspace, with the transition when there is one. */
export function useGoToWorkspace(): () => void {
  return useContext(GoToWorkspaceContext)
}
