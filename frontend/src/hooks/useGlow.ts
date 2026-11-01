import { useEffect, useRef } from 'react'
import type { RefObject } from 'react'

/** The glow starts to respond when the pointer comes within this many pixels of the element. */
const REACH = 240

/** How far the colors swing as the pointer crosses the window, in degrees around the color wheel. */
const HUE_SWING = 140

/**
 * Makes a "glow pill" (see `glow-pill` in styles/index.css) react to the
 * pointer. Attach the ref this returns to the element.
 *
 * The hook only measures; the stylesheet does the drawing. On every pointer
 * move it writes four numbers onto the element as CSS variables:
 *
 *   --glow-x, --glow-y   where the pointer is, measured from the element's
 *                        top-left corner (a bright spot is drawn there)
 *   --glow-near          0 when the pointer is far away, rising to 1 as it
 *                        arrives (the glow brightens)
 *   --glow-hue           how far to shift the colors, from the pointer's
 *                        left-to-right position in the window
 *
 * Pass `enabled = false` to do nothing (used by buttons that are not glowing).
 * On touch screens there is no pointer to follow, so the pill just keeps its
 * slow turning colors.
 */
export function useGlow<T extends HTMLElement>(enabled = true): RefObject<T | null> {
  const elementRef = useRef<T>(null)

  useEffect(() => {
    const element = elementRef.current
    if (!enabled || !element) {
      return
    }

    let frameId = 0
    let pointerX = 0
    let pointerY = 0

    const update = () => {
      frameId = 0
      const box = element.getBoundingClientRect()

      // How far the pointer is from the nearest edge of the element (0 when it is over it).
      const outsideX = Math.max(box.left - pointerX, 0, pointerX - box.right)
      const outsideY = Math.max(box.top - pointerY, 0, pointerY - box.bottom)
      const distance = Math.hypot(outsideX, outsideY)
      const near = Math.max(1 - distance / REACH, 0)

      element.style.setProperty('--glow-x', `${pointerX - box.left}px`)
      element.style.setProperty('--glow-y', `${pointerY - box.top}px`)
      element.style.setProperty('--glow-near', near.toFixed(3))
      element.style.setProperty('--glow-hue', ((pointerX / window.innerWidth - 0.5) * HUE_SWING).toFixed(1))
    }

    const onPointerMove = (event: PointerEvent) => {
      pointerX = event.clientX
      pointerY = event.clientY
      // Pointer events can arrive faster than the screen redraws. Do the
      // measuring at most once per redraw.
      if (frameId === 0) {
        frameId = requestAnimationFrame(update)
      }
    }

    window.addEventListener('pointermove', onPointerMove, { passive: true })
    return () => {
      window.removeEventListener('pointermove', onPointerMove)
      cancelAnimationFrame(frameId)
    }
  }, [enabled])

  return elementRef
}
