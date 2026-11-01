/**
 * Whether an AI model is thinking somewhere on the page right now (writing
 * brief suggestions, for example), so the studio can show that it is waiting.
 * Each part of the page that waits on a model says so with useModelThinking
 * (hooks/useModelThinking.ts); the studio reads the total.
 */
type Listener = (thinking: boolean) => void

let waiting = 0
const listeners = new Set<Listener>()

function announce() {
  for (const listener of listeners) listener(waiting > 0)
}

/** One more thing is waiting for a model; returns the function to call when it is done. */
export function startWaiting(): () => void {
  waiting += 1
  announce()
  let done = false
  return () => {
    if (done) return
    done = true
    waiting -= 1
    announce()
  }
}

export function isModelThinking(): boolean {
  return waiting > 0
}

export function onModelThinking(listener: Listener): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}
