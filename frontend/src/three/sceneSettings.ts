/**
 * Numbers shared by more than one part of the hero scene.
 *
 * The scene is measured in metres, so sizes can be checked against real
 * furniture: the desk top is 0.74 m high, the laptop is 0.325 m wide.
 *
 * Axes (three.js convention):
 *   x  left (-) to right (+)
 *   y  down (-) to up (+)
 *   z  away from the viewer (-) to toward the viewer (+)
 *
 * The desk stands at the origin (0, 0, 0), on the flat top of the hill.
 */

/** The desk. */
export const DESK = {
  width: 1.36,
  depth: 0.76,
  /** Height of the top surface above the ground. */
  topHeight: 0.74,
  topThickness: 0.035,
} as const

/** The laptop, sitting on the desk a little behind its center. */
export const LAPTOP = {
  width: 0.325,
  depth: 0.225,
  baseThickness: 0.014,
  lidHeight: 0.215,
  /** How far the open screen leans back from upright, in radians (about 14 degrees). */
  lidLean: 0.25,
  /** Position of the laptop's center on the desk (x, z). */
  position: { x: 0, z: -0.06 },
} as const

/** Where the chair stands, and which way it faces. */
export const CHAIR = {
  position: { x: -0.92, z: 0.78 },
  /** Turned so the seat faces the desk and its back faces the viewer. */
  rotationY: 2.56,
} as const

/**
 * The camera's journey. Scrolling moves it along a straight line from the
 * wide opening shot to a close-up of the laptop.
 */
export const CAMERA = {
  /** Vertical field of view in degrees. Small = a flat, telephoto look. */
  fieldOfView: 30,

  /** Opening shot: standing back, seeing the whole hilltop. */
  start: { height: 1.7, distance: 8.1, lookAtHeight: 1.32 },

  /** Closing shot: leaning in over the desk, the laptop filling the middle of the frame. */
  end: { height: 1.0, distance: 0.84, lookAtHeight: 0.865 },

  /**
   * On a tall phone screen the same distance would crop the sides, so the
   * camera stands farther back: distances are multiplied by up to these values.
   */
  tallScreen: { startDistanceScale: 1.75, endDistanceScale: 2.4, extraLookAtHeight: 1.1 },

  /** How far the camera drifts with the pointer in the opening shot, in metres. */
  pointerDrift: { x: 0.45, y: 0.16 },
} as const

/**
 * How the painted backdrop changes by the end of the zoom. The backdrop is a
 * flat picture, so these numbers imitate what a real landscape would do as
 * the camera moves in and tilts down toward the desk.
 */
export const BACKDROP_ZOOM = {
  /** 1.0 = unchanged. The mountains loom a little larger as the camera moves in. */
  endScale: 1.2,
  /** How far the picture slides up the screen (0.18 = 18% of its height) as the camera tilts down. */
  endRise: 0.18,
  /** 0 = sharp, 1 = fully out of focus, like a camera focused on a near object. */
  endBlur: 1,
} as const
