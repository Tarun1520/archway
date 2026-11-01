/** The id of the idea input on the start screen. The form sets it; this helper finds it. */
export const IDEA_INPUT_ID = 'idea'

/** The id of the start screen, the section that holds the idea form. */
export const START_SECTION_ID = 'start'

/** Where "Start a project" links point. */
export const START_HREF = `#${START_SECTION_ID}`

/** How often, and for how long, to keep trying to focus the input. */
const RETRY_EVERY_MS = 150
const GIVE_UP_AFTER_MS = 6000

/**
 * Puts the keyboard cursor in the idea input.
 *
 * "Start a project" links point to START_HREF, which scrolls to the start
 * screen. Calling this from their `onClick` as well means the person can
 * start typing as soon as they arrive.
 *
 * WHY IT RETRIES
 *   A browser refuses to focus something that is not visible. When the link
 *   is clicked from the top of the page, the start screen is still a small
 *   picture on the laptop in the video, or not shown at all. So this tries
 *   again every moment until the focus takes, and gives up after a few
 *   seconds.
 *
 *   `preventScroll` stops the browser from jumping to the input instantly,
 *   which would cut the smooth scroll short.
 */
export function focusIdeaInput(): void {
  const startedAt = Date.now()

  const attempt = () => {
    const input = document.getElementById(IDEA_INPUT_ID)
    input?.focus({ preventScroll: true })

    const focused = document.activeElement === input
    if (!focused && Date.now() - startedAt < GIVE_UP_AFTER_MS) {
      window.setTimeout(attempt, RETRY_EVERY_MS)
    }
  }

  // The first try waits a moment, because following an in-page link makes
  // the browser clear the current focus first.
  window.setTimeout(attempt, 0)
}
