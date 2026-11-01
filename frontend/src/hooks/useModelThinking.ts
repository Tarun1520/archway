import { useEffect, useState } from 'react'
import { isModelThinking, onModelThinking, startWaiting } from '../lib/modelActivity'

/** Tells the page a model is thinking for as long as `active` is true (lib/modelActivity.ts). */
export function useModelThinking(active: boolean): void {
  useEffect(() => {
    if (!active) return
    return startWaiting()
  }, [active])
}

/** True while any part of the page is waiting for a model. */
export function useAnyModelThinking(): boolean {
  const [thinking, setThinking] = useState(isModelThinking)
  useEffect(() => onModelThinking(setThinking), [])
  return thinking
}
