/**
 * What happens when someone submits an idea on the welcome page.
 *
 * This is the single seam between the welcome page and the rest of the app.
 * Today the studio workspace and the backend do not exist yet, so the idea is
 * only kept in this browser tab. When the backend is ready, this function is
 * the one place that changes (it will create a project through the API), and
 * the form that calls it stays the same.
 */

/** Where the idea is kept until the studio workspace can pick it up. */
export const PENDING_IDEA_KEY = 'archway.pendingIdea'

/** Long enough for a detailed paragraph, short enough to stop accidental pastes of whole files. */
export const MAX_IDEA_LENGTH = 2000

export type StartProjectResult =
  | { ok: true; idea: string }
  | { ok: false; reason: 'empty' | 'too_long' | 'storage_unavailable' }

/** The one method of browser storage this function needs. Tests pass a fake. */
type IdeaStorage = Pick<Storage, 'setItem'>

export function startProject(rawIdea: string, storage?: IdeaStorage): StartProjectResult {
  const idea = rawIdea.trim()

  if (idea.length === 0) {
    return { ok: false, reason: 'empty' }
  }
  if (idea.length > MAX_IDEA_LENGTH) {
    return { ok: false, reason: 'too_long' }
  }

  try {
    // sessionStorage lasts until the tab is closed and never leaves the browser.
    const target = storage ?? window.sessionStorage
    target.setItem(PENDING_IDEA_KEY, idea)
  } catch {
    // Storage can be blocked (private mode, strict settings). Say so instead
    // of pretending the idea was kept.
    return { ok: false, reason: 'storage_unavailable' }
  }

  return { ok: true, idea }
}
