/**
 * How far the page has scrolled through a pinned "track".
 *
 * The hero sits inside a tall section (the track) and stays pinned to the
 * window while the page scrolls through it. This returns a number that
 * describes where in that journey the page is:
 *
 *   0  the top of the track is at the top of the window (nothing scrolled)
 *   1  the hero is about to un-pin (the track's end has reached the hero's end)
 *
 * Both hero backdrops (the 3D scene and the video) are driven by this number.
 *
 * `stageHeight` is the height of the pinned hero. It is passed in rather than
 * read from the window, because on a phone the window's height changes as
 * the browser's toolbars slide in and out, while the hero's does not.
 */
export function trackProgress(track: HTMLElement | null, stageHeight: number): number {
  if (!track) {
    return 0
  }

  // The distance the page can scroll while the hero stays pinned.
  const travel = track.offsetHeight - stageHeight
  if (travel <= 0) {
    return 0 // the track is not taller than the hero: nothing to scroll through
  }

  const scrolled = -track.getBoundingClientRect().top
  return Math.min(Math.max(scrolled / travel, 0), 1)
}
