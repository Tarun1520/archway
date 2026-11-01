import { createContext, useContext } from 'react'

/**
 * True while something covers the whole page: the welcome-to-workspace film (components/transition/SpaceTransition.tsx).
 *
 * The workspace opens UNDER the film, so anything that should be seen as the person arrives (the agents coming onto
 * the stage) waits until this turns false. Outside the transition it is always false.
 */
export const CurtainContext = createContext(false)

export function useCurtain(): boolean {
  return useContext(CurtainContext)
}
