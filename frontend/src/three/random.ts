/**
 * A random number generator that gives the SAME sequence every time for the
 * same seed.
 *
 * `Math.random()` is different on every page load, which would move every
 * blade of grass each time. With a seed, the meadow is identical on each visit.
 * (The algorithm is a well-known small one called "mulberry32".)
 *
 * Usage:
 *   const random = createRandom(7)
 *   random() // a number from 0 (inclusive) to 1 (exclusive)
 */
export function createRandom(seed: number): () => number {
  let state = seed >>> 0

  return () => {
    state = (state + 0x6d2b79f5) >>> 0
    let mixed = state
    mixed = Math.imul(mixed ^ (mixed >>> 15), mixed | 1)
    mixed ^= mixed + Math.imul(mixed ^ (mixed >>> 7), mixed | 61)
    return ((mixed ^ (mixed >>> 14)) >>> 0) / 4294967296
  }
}
