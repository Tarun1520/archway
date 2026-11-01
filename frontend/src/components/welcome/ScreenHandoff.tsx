import { useEffect, useRef } from 'react'
import type { ReactNode } from 'react'
import { heroMedia } from '../../content/heroMedia'
import { displayInsets, heroScreenTrack } from '../../content/heroScreenTrack'
import { usePrefersReducedMotion } from '../../hooks/usePrefersReducedMotion'
import { heroPlayback } from '../../lib/heroPlayback'
import { hasArrived, placeOnScreen, screenRectAt } from '../../lib/screenHandoff'

interface ScreenHandoffProps {
  /** Everything on the page that comes after the hero. */
  children: ReactNode
}

/**
 * Makes the rest of the page appear ON the laptop's screen in the hero clip,
 * grow with it as the camera closes in, and end up as the page itself.
 *
 * HOW IT WORKS
 *   1. A "holder" keeps the place of every section after the hero. It is
 *      pulled up by one window height, so its place at the very end of the
 *      hero's scroll is exactly the window.
 *   2. While the hero is still pinned, the page inside the holder is pinned
 *      to the window too, so scrolling cannot move it. On every frame it is
 *      shrunk and moved (a CSS "transform") so
 *      that it sits on the laptop's display, using the measurements in
 *      content/heroScreenTrack.ts. This is true from the very first frame,
 *      before any scrolling: the small laptop in the opening shot is already
 *      showing the page.
 *   3. As the display grows to fill the window, the shrink shrinks to nothing
 *      and the move goes to zero. The page is then full size exactly where
 *      the holder is, so it is un-pinned and scrolls on as normal. Nothing
 *      is swapped: it was the real page all along.
 *
 * The page is shrunk to the display's WIDTH, and whatever does not fit the
 * display's height is cut off. On a wide window that shows nearly the whole
 * first screen; on a tall phone it shows the top part of it.
 *
 * Without a hero clip, or with reduced motion on, this does nothing and the
 * sections simply follow the hero.
 */
export function ScreenHandoff({ children }: ScreenHandoffProps) {
  const holderRef = useRef<HTMLDivElement>(null)
  const pageRef = useRef<HTMLDivElement>(null)
  const reduceMotion = usePrefersReducedMotion()
  const active = Boolean(heroMedia.videoSrc) && !reduceMotion

  useEffect(() => {
    const holder = holderRef.current
    const page = pageRef.current
    if (!active || !holder || !page) {
      return
    }

    let frameId = 0
    let wasPlaced = false

    // While the page is pinned (see below) it no longer takes up room in the
    // document, so the holder is given the page's height to keep the room.
    const keepRoom = new ResizeObserver(() => {
      holder.style.height = `${page.offsetHeight}px`
    })
    keepRoom.observe(page)

    /** Puts the page back to being an ordinary part of the document. */
    const release = () => {
      if (!wasPlaced) {
        return
      }
      page.style.position = ''
      page.style.transform = ''
      page.style.clipPath = ''
      page.style.visibility = ''
      page.inert = false
      wasPlaced = false
    }

    const tick = () => {
      frameId = requestAnimationFrame(tick)

      // Where the page's top would be in the window if it were left alone.
      const naturalTop = holder.offsetTop - window.scrollY

      // Once it has reached the top of the window, the hero's scroll is over.
      if (naturalTop <= 0) {
        release()
        return
      }

      // PIN THE PAGE TO THE WINDOW.
      // `position: fixed` takes it out of the scrolling document altogether,
      // so scrolling cannot move it. Only the numbers below do. (Before this,
      // the page scrolled with the document and was nudged back into place
      // once per frame. The browser scrolls between frames, so the page
      // visibly bobbed up and down on the laptop.)
      wasPlaced = true
      page.style.position = 'fixed'

      // Until the video has loaded there is no laptop to draw on yet.
      if (heroPlayback.duration === 0) {
        page.style.visibility = 'hidden'
        page.inert = true
        return
      }

      // The box the picture fills. On a phone this is not always the window's
      // size, so it is taken from the hero itself.
      const viewport = { width: heroPlayback.stageWidth, height: heroPlayback.stageHeight }
      const video = { width: heroPlayback.width, height: heroPlayback.height }
      const display = screenRectAt(heroPlayback.time, heroScreenTrack, displayInsets)

      // `heroPlayback` also says how the video itself is being drawn (a
      // little enlarged, nudged by the pointer), so the page moves with it
      // and never slides around on the laptop.
      const placement = placeOnScreen(display, viewport, video, heroPlayback)

      // Move to the display's corner, then shrink. The shrink happens around
      // the top-left corner because of `origin-top-left` on the element.
      page.style.transform = `translate3d(${placement.x}px, ${placement.y}px, 0) scale(${placement.scale})`
      page.style.visibility = 'visible'

      // While it is a picture on a screen it must not be usable: not
      // clickable, and not reachable with the Tab key (`inert` does both).
      // Once it fills the window it is the page, and it is usable.
      page.inert = !hasArrived(placement, viewport)

      // Show only the part of the page that fits on the display: cut off
      // everything below it. Measured in the page's own (unshrunk) pixels.
      const visiblePagePixels = placement.visibleHeight / placement.scale
      const hiddenBelow = Math.max(page.offsetHeight - visiblePagePixels, 0)
      page.style.clipPath = `inset(0px 0px ${hiddenBelow}px 0px)`
    }

    frameId = requestAnimationFrame(tick)

    return () => {
      cancelAnimationFrame(frameId)
      keepRoom.disconnect()
      holder.style.height = ''
      release()
    }
  }, [active])

  // The light "morning" colors for every screen after the hero.
  const morning = 'bg-dawn text-ink'

  if (!active) {
    return <div className={morning}>{children}</div>
  }

  return (
    // The holder keeps the page's place in the document. -mt-[100svh] pulls
    // it up one window height; z-20 puts it above the hero.
    <div ref={holderRef} className="relative z-20 -mt-[100svh]">
      {/*
        The page itself. `top-0 left-0 w-full` only matter while it is pinned
        (position: fixed); the solid background makes it read as a lit screen.
      */}
      <div ref={pageRef} data-pinned-page className={`top-0 left-0 w-full origin-top-left will-change-transform ${morning}`}>
        {children}
      </div>
    </div>
  )
}
