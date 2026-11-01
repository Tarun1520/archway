/**
 * Which hero the welcome page shows.
 *
 * The hero can be drawn in two ways:
 *
 *   1. A filmed clip that moves forward and backward as the page scrolls
 *      (used when `videoSrc` below is filled in). The realism comes from the
 *      footage.
 *   2. A live 3D scene drawn by three.js (used when `videoSrc` is empty).
 *
 * TO USE A NEW CLIP
 *   1. From the frontend folder, run:
 *        swift scripts/prepare-hero-video.swift <your-clip.mp4>
 *      It writes public/hero/hero-scrub.mp4 and public/hero/hero-poster.jpg.
 *      The script's opening comments list its options, including how the
 *      large (2560 x 1440) and small (1280 x 720) copies were made.
 *      (The current clip was prepared with `--erase-mark 1118,558,84,84`
 *      added, which lifts the generator's corner logo off every frame. The
 *      script's own comments explain how.)
 *   2. Measure where the laptop screen is in the new clip. This rewrites
 *      heroScreenTrack.ts:
 *        swift scripts/track-hero-screen.swift public/hero/hero-scrub.mp4 > src/content/heroScreenTrack.ts
 *
 * What a clip should be: one continuous camera move with no cuts, from the
 * wide opening shot straight in to the laptop, ending with the laptop's dark
 * screen filling the whole frame.
 */
export const heroMedia = {
  /**
   * The clip, as a path inside frontend/public. Leave empty ('') to use the
   * live 3D scene. This one is 2560 x 1440 (about 39 MB), for computer screens.
   * It was enlarged from the 1280 x 720 original, so it is a cleaner picture
   * on a big screen but holds no extra detail.
   */
  videoSrc: '/hero/hero-scrub.mp4',

  /**
   * The same clip at 1280 x 720 (about 13 MB), used on phone-sized screens.
   * A phone's screen is small, so the larger file would be slower to load
   * and to step through, for no visible gain. Leave empty ('') to always use
   * the large one.
   */
  videoSrcSmall: '/hero/hero-scrub-720.mp4',

  /** Screens whose shorter side is below this many pixels get the small clip. */
  smallScreenBelow: 700,

  /** The clip's first frame, shown while the video loads. */
  posterSrc: '/hero/hero-poster.jpg',

  /**
   * How much scrolling the clip takes, in window heights. The hero stays
   * pinned for this long while the clip plays. Longer = a slower, calmer zoom.
   */
  scrollLengthInScreens: 2,
}

/**
 * The pointer nudges the video a few pixels in the opening part of the clip.
 * That nudge fades away between these two moments (seconds into the clip),
 * so that by the time the laptop's screen is large, the page drawn on it and
 * the picture are perfectly still relative to each other.
 */
export const pointerNudgeFades = { from: 3.0, to: 4.2 }
