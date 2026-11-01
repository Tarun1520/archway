/**
 * A tiny message line to the studio's background grid (BackgroundRipple.tsx):
 * anything on the page can ask for a ripple at a point on the screen, without
 * knowing where the grid lives. Points are in window (client) pixels.
 */
type Listener = (x: number, y: number) => void

const listeners = new Set<Listener>()

/** Listens for ripple requests; returns the function that stops listening. */
export function onRippleRequest(listener: Listener): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

/** Asks the background grid for one ripple centred on (x, y). */
export function requestRipple(x: number, y: number): void {
  for (const listener of listeners) listener(x, y)
}
