/**
 * Picking up the idea typed on the welcome page.
 *
 * The welcome page's `startProject` keeps the idea in this browser tab under
 * PENDING_IDEA_KEY. When the studio opens, it takes the idea from there and
 * turns it into a real project through the backend.
 */
import { PENDING_IDEA_KEY } from './startProject'

/** The two methods of browser storage this needs. Tests pass a fake. */
type IdeaStorage = Pick<Storage, 'getItem' | 'removeItem'>

/**
 * Returns the waiting idea and removes it, so it is only ever used once.
 * Returns null when there is none (or storage is blocked).
 */
export function takePendingIdea(storage?: IdeaStorage): string | null {
  try {
    const target = storage ?? window.sessionStorage
    const idea = target.getItem(PENDING_IDEA_KEY)
    if (idea === null) return null
    target.removeItem(PENDING_IDEA_KEY)
    return idea.trim() === '' ? null : idea
  } catch {
    return null
  }
}

/** A short project name made from the first words of an idea. */
export function projectNameFromIdea(idea: string, maxLength = 60): string {
  const oneLine = idea.replace(/\s+/g, ' ').trim()
  if (oneLine.length <= maxLength) return oneLine

  // Cut at the last space before the limit, so a word is never chopped in half.
  const cut = oneLine.slice(0, maxLength)
  const lastSpace = cut.lastIndexOf(' ')
  const tidy = lastSpace > maxLength / 2 ? cut.slice(0, lastSpace) : cut
  return `${tidy}…`
}
