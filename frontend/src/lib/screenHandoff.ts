/**
 * The geometry behind the screen hand-off: pure calculations, no page access,
 * so they can be tested on their own (see screenHandoff.test.ts).
 *
 * THE IDEA
 *   The page is shown as if it were on the laptop's screen in the video. It
 *   is shrunk and moved so it sits exactly on the screen, and it grows as the
 *   camera closes in. When the screen fills the window, the page is at its
 *   full size in its normal place: it has become the page.
 */
import type { ScreenKeyframe } from '../content/heroScreenTrack'

/**
 * Tall, narrow windows (phones held upright) are treated differently, because
 * they show only the middle slice of the wide video.
 */
export const NARROW_WINDOW = {
  /** A window counts as narrow when its width divided by its height is below this. */
  belowShape: 1.3,
  /**
   * On narrow windows the video is drawn this much larger, growing downward
   * from its top edge. That moves the desk lower, clear of the buttons.
   */
  videoZoom: 1.18,
}

/** True if the window is tall and narrow. */
export function isNarrowWindow(viewport: { width: number; height: number }): boolean {
  return viewport.width / viewport.height < NARROW_WINDOW.belowShape
}

/** A rectangle inside the video frame, as fractions of the frame (0 to 1, possibly beyond). */
export interface FrameRect {
  left: number
  top: number
  right: number
  bottom: number
}

export interface Size {
  width: number
  height: number
}

/** How to draw the page so it sits on the laptop's screen. All values are in window pixels. */
export interface ScreenPlacement {
  /** 1 = full size. Below 1 = shrunk to fit the screen's width. */
  scale: number
  /** Where the page's top-left corner goes. */
  x: number
  y: number
  /** How much of the page's height is showing through the screen. */
  visibleHeight: number
}

/** Blends smoothly from 0 to 1 as `value` goes from `start` to `end`. */
export function smoothstep(start: number, end: number, value: number): number {
  const t = Math.min(Math.max((value - start) / (end - start), 0), 1)
  return t * t * (3 - 2 * t)
}

/**
 * Where the laptop's display is at a given moment of the clip.
 *
 * The keyframes are measurements at certain moments. For a moment in between
 * two of them, this blends the two measurements in proportion.
 */
export function screenRectAt(
  time: number,
  keyframes: readonly ScreenKeyframe[],
  insets: { left: number; right: number; top: number; bottom: number },
): FrameRect {
  const first = keyframes[0]
  const last = keyframes[keyframes.length - 1]

  let from = first
  let to = last
  if (time <= first[0]) {
    to = first
  } else if (time >= last[0]) {
    from = last
  } else {
    // Find the two measurements on either side of `time`.
    for (let index = 0; index < keyframes.length - 1; index++) {
      if (time >= keyframes[index][0] && time <= keyframes[index + 1][0]) {
        from = keyframes[index]
        to = keyframes[index + 1]
        break
      }
    }
  }

  const span = to[0] - from[0]
  const amount = span > 0 ? (time - from[0]) / span : 0
  const blend = (edge: 1 | 2 | 3 | 4) => from[edge] + (to[edge] - from[edge]) * amount

  const left = blend(1)
  const top = blend(2)
  const right = blend(3)
  const bottom = blend(4)

  // Trim off the black frame around the display.
  const width = right - left
  const height = bottom - top
  return {
    left: left + width * insets.left,
    top: top + height * insets.top,
    right: right - width * insets.right,
    bottom: bottom - height * insets.bottom,
  }
}

/**
 * How the video element itself is being drawn: enlarged by `zoom` (growing
 * from the middle of its top edge) and shifted by a few pixels.
 */
export interface VideoNudge {
  zoom: number
  shiftX: number
  shiftY: number
}

const NO_NUDGE: VideoNudge = { zoom: 1, shiftX: 0, shiftY: 0 }

/**
 * Works out how to draw the page on the laptop's display.
 *
 * The video fills the window the way a background photo does ("cover"): it
 * is scaled until it covers the whole window, and whatever overflows is cut
 * off equally on both sides. The first half of this function redoes that
 * arithmetic to find where the display ends up in the window.
 */
export function placeOnScreen(display: FrameRect, viewport: Size, video: Size, nudge: VideoNudge = NO_NUDGE): ScreenPlacement {
  // 1. How the video is fitted into the window.
  const fit = Math.max(viewport.width / video.width, viewport.height / video.height)
  const shownWidth = video.width * fit
  const shownHeight = video.height * fit
  const offsetX = (viewport.width - shownWidth) / 2
  const offsetY = (viewport.height - shownHeight) / 2

  // 2. The display's edges in window pixels, moved the same way the video
  //    element is: shifted, then enlarged from the middle of the top edge.
  const middle = viewport.width / 2
  const moveX = (x: number) => middle + nudge.zoom * (x - middle + nudge.shiftX)
  const moveY = (y: number) => nudge.zoom * (y + nudge.shiftY)

  const left = moveX(offsetX + display.left * shownWidth)
  const right = moveX(offsetX + display.right * shownWidth)
  const top = moveY(offsetY + display.top * shownHeight)
  const bottom = moveY(offsetY + display.bottom * shownHeight)

  // 3. Shrink the page so its width matches the display's width. Once the
  //    display is wider than the window, stop at full size: the page is never
  //    drawn larger than life.
  const scale = Math.min((right - left) / viewport.width, 1)
  const fullSize = scale >= 1

  // An edge that has left the window is treated as being at the window's edge.
  const x = fullSize ? 0 : left
  const y = Math.max(top, 0)
  const visibleHeight = Math.max(Math.min(bottom, viewport.height) - y, 0)

  return { scale, x, y, visibleHeight }
}

/** True once the page fills the window at full size: it has stopped being a picture on a screen. */
export function hasArrived(placement: ScreenPlacement, viewport: Size): boolean {
  return placement.scale >= 1 && placement.y <= 0 && placement.visibleHeight >= viewport.height
}
