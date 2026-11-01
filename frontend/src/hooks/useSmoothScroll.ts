import { useEffect } from 'react'
import Lenis from 'lenis'
import { landingPosition } from '../lib/inPageLinks'

/** How long a link's scroll takes: longer for longer journeys, within these limits (seconds). */
const SHORTEST_SCROLL = 0.8
const LONGEST_SCROLL = 2.4
const PIXELS_PER_SECOND = 1100

/**
 * Sets up scrolling for the whole page:
 *
 *   1. Smooth scrolling, using Lenis. Lenis still scrolls the real page (so
 *      keyboard scrolling and screen readers keep working); it only eases the
 *      movement. Pass `smooth = false` to leave the browser's normal scrolling
 *      untouched, which is what people who ask for reduced motion should get.
 *
 *   2. In-page links (href="#something"). These are handled here rather than
 *      left to the browser, because the browser would scroll to the wrong
 *      place while the page is drawn on the laptop in the hero (see
 *      lib/inPageLinks.ts for why).
 */
export function useSmoothScroll(smooth: boolean): void {
  useEffect(() => {
    const lenis = smooth ? new Lenis({ autoRaf: true }) : null

    /** Scrolls so the element with this id is in place. Returns false if there is no such element. */
    const goTo = (id: string, animate: boolean): boolean => {
      const target = document.getElementById(id)
      if (!target) {
        return false
      }
      const top = landingPosition(target)

      if (lenis && animate) {
        const distance = Math.abs(top - window.scrollY)
        const duration = Math.min(Math.max(distance / PIXELS_PER_SECOND, SHORTEST_SCROLL), LONGEST_SCROLL)
        lenis.scrollTo(top, { duration })
      } else if (lenis) {
        lenis.scrollTo(top, { immediate: true })
      } else {
        window.scrollTo(0, top)
      }
      return true
    }

    const onClick = (event: MouseEvent) => {
      // Leave alone anything that is not a plain left click (for example
      // Cmd-click, which means "open in a new tab").
      if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
        return
      }

      const link = (event.target as Element | null)?.closest('a[href^="#"]')
      const id = link?.getAttribute('href')?.slice(1)
      if (!id) {
        return
      }

      if (goTo(id, true)) {
        event.preventDefault() // we did the scrolling; the browser should not also jump
        history.pushState(null, '', `#${id}`) // keep the address bar and the Back button in step
      }
    }
    document.addEventListener('click', onClick)

    // If the page was opened with a link to a section (…/#principles), the
    // browser's own jump may have gone to the wrong place. Go to the right one.
    const idInAddress = window.location.hash.slice(1)
    const firstFrame = requestAnimationFrame(() => {
      if (idInAddress) {
        goTo(idInAddress, false)
      }
    })

    return () => {
      cancelAnimationFrame(firstFrame)
      document.removeEventListener('click', onClick)
      lenis?.destroy()
    }
  }, [smooth])
}
