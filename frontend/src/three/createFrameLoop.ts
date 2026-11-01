/**
 * A tiny animation loop.
 *
 * `requestAnimationFrame` asks the browser to call a function right before it
 * next repaints the screen (about 60 times a second). Calling it again from
 * inside that function creates a loop. This helper wraps that pattern with
 * `start` and `stop`, so the loop can be paused while the hero is off screen.
 */
export interface FrameLoop {
  start(): void
  stop(): void
}

export function createFrameLoop(onFrame: (timeSeconds: number) => void): FrameLoop {
  let frameId: number | null = null

  const tick = (timeMs: number) => {
    onFrame(timeMs / 1000)
    frameId = requestAnimationFrame(tick)
  }

  return {
    start() {
      if (frameId === null) {
        frameId = requestAnimationFrame(tick)
      }
    },
    stop() {
      if (frameId !== null) {
        cancelAnimationFrame(frameId)
        frameId = null
      }
    },
  }
}
