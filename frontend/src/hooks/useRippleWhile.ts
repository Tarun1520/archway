import { useEffect } from 'react'
import { requestRipple } from '../lib/rippleBus'

/**
 * While `active`, sends a ripple through the background grid every `everyMs`,
 * centred on the first of `anchors` that is on screen. An anchor is an element
 * marked `data-ripple-anchor="<name>"` (the stage headline, the lead robot,
 * the content panel). It stops as soon as `active` turns false.
 *
 * This is how the studio shows it is WAITING: a model thinking, or the agents
 * at work. People who ask for reduced motion get no ripples (the grid ignores
 * them).
 */
export function useRippleWhile(active: boolean, anchors: string[], everyMs = 1600): void {
  const key = anchors.join(',')
  useEffect(() => {
    if (!active) return
    const fire = () => {
      for (const name of key.split(',')) {
        const element = document.querySelector(`[data-ripple-anchor="${name}"]`)
        if (!element) continue
        const box = element.getBoundingClientRect()
        const x = box.left + box.width / 2
        const y = box.top + box.height / 2
        const onScreen = box.width > 0 && x >= 0 && y >= 0 && x <= window.innerWidth && y <= window.innerHeight
        if (!onScreen) continue
        requestRipple(x, y)
        return
      }
    }
    fire()
    const timer = window.setInterval(fire, everyMs)
    return () => window.clearInterval(timer)
  }, [active, key, everyMs])
}
