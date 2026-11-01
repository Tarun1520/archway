/**
 * A small shared notebook about the hero clip: which moment is on screen
 * right now, and how big the clip is.
 *
 * The video backdrop writes to it on every frame. The screen hand-off reads
 * from it, so the page drawn on the laptop stays glued to the picture.
 *
 * It is a plain object on purpose. These values change sixty times a second,
 * and putting them in React state would re-draw the whole page that often.
 */
export const heroPlayback = {
  /** The moment of the clip being shown, in seconds. */
  time: 0,
  /** The clip's length in seconds. 0 until the browser has read the file's header. */
  duration: 0,
  /** The clip's picture size in pixels. 0 until known. */
  width: 0,
  height: 0,
  /**
   * How the video element is being drawn right now: enlarged by `zoom`
   * (growing from the middle of its top edge) and shifted by this many
   * pixels. Anything placed on top of the picture must be moved the same way.
   */
  zoom: 1,
  shiftX: 0,
  shiftY: 0,
  /**
   * The size of the hero itself (the box the picture fills), in pixels.
   * On a phone this can differ from the window's size, because the browser's
   * toolbars slide in and out. 0 until measured.
   */
  stageWidth: 0,
  stageHeight: 0,
}
