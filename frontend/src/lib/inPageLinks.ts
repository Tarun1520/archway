/**
 * Working out where an in-page link (like "#how-it-works") should scroll to.
 *
 * WHY THIS EXISTS
 *   Normally the browser does this itself. But during the hero's zoom, the
 *   sections after the hero are drawn shrunk onto the laptop's screen. If the
 *   browser is asked "where is #how-it-works?" at that moment, it answers
 *   with where the shrunk picture is, and scrolls to the wrong place.
 *
 *   The functions here ask a different question: where does the section sit
 *   in the page's real layout? That answer does not change when something is
 *   drawn shrunk or moved.
 */

/** Space left above a section when a link lands on it, so its heading clears the top bar. */
const SPACE_ABOVE = 24

/**
 * How far down the page an element starts, in pixels, in the page's layout.
 *
 * `offsetTop` gives an element's distance from its "offset parent" (the
 * nearest positioned ancestor), ignoring any shrinking or moving applied for
 * display. Adding those distances up, parent by parent, reaches the page top.
 */
export function documentTop(element: HTMLElement): number {
  let top = 0
  let current: HTMLElement | null = element
  while (current) {
    // The page after the hero is pinned to the window during the hero's zoom
    // (ScreenHandoff.tsx). A pinned element reports no offset parent and its
    // own offset means nothing, so step out to the holder around it, which
    // still sits in the document where the page belongs.
    if (current.hasAttribute('data-pinned-page')) {
      current = current.parentElement
      continue
    }
    top += current.offsetTop
    current = current.offsetParent as HTMLElement | null
  }
  return top
}

/**
 * The scroll position a link to `target` should end at.
 *
 * Sections that fill the whole window (marked with `data-fills-window`) land
 * exactly at their top. Other sections land a little lower, leaving
 * SPACE_ABOVE so the previous section is hinted at and nothing is cramped.
 */
export function landingPosition(target: HTMLElement): number {
  const fillsWindow = target.hasAttribute('data-fills-window')
  return Math.max(documentTop(target) - (fillsWindow ? 0 : SPACE_ABOVE), 0)
}
