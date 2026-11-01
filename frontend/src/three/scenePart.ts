import type { Object3D } from 'three'

/**
 * The contract every piece of the hero scene follows (backdrop, hill, grass,
 * desk, chair, laptop, lights, ...).
 *
 * Because each piece has the same shape, the scene can treat them as a plain
 * list: to add a new piece, write a `createSomething()` that returns a
 * ScenePart and add it to the list in createHeroScene.ts. To remove one,
 * delete it from that list. Nothing else changes.
 */
export interface ScenePart {
  /** The thing to add to the three.js scene. */
  object: Object3D
  /** Called before every frame with the time in seconds. Leave out if the part never moves. */
  update?(timeSeconds: number): void
  /** Called when the drawing size changes, in real device pixels. */
  setResolution?(width: number, height: number): void
  /** Called with the eased pointer position, -1 to 1 on each axis. */
  setPointer?(x: number, y: number): void
  /** Called with how far the scroll zoom has gone: 0 = opening shot, 1 = close-up. */
  setZoom?(progress: number): void
  /** Release the graphics memory this part holds. */
  dispose(): void
}
