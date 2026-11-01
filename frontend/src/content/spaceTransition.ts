/**
 * The short film that plays between the welcome page and the workspace.
 * The file is made by scripts/prepare-transition-video.swift (logo lifted off,
 * 1080p, sound faded in and out).
 */
export const spaceTransition = {
  src: '/transition/space-transition.mp4',
  /** How long before the film ends the workspace starts to show through, in seconds. */
  revealSeconds: 0.9,
  /** How long the fade takes when someone presses Skip, in seconds. */
  skipSeconds: 0.45,
  skipLabel: 'Skip',
  label: 'Opening the workspace',
}
