import { useEffect, useRef, useState } from 'react'
import type { RefObject } from 'react'
import { usePrefersReducedMotion } from '../../hooks/usePrefersReducedMotion'
import { trackProgress } from '../../lib/trackProgress'

/** A fixed moment in the animation, used when motion is reduced and only one frame is drawn. */
const STILL_FRAME_TIME = 12

/** How quickly the picture follows the pointer each frame (0 = never, 1 = instantly). */
const POINTER_EASING = 0.05

interface HeroBackdropProps {
  /**
   * The tall section the hero is pinned inside. How far the page has scrolled
   * through it decides how far the camera has zoomed.
   */
  trackRef: RefObject<HTMLElement | null>
}

/**
 * The moving picture behind the hero text.
 *
 * This component is the glue between React and the three.js scene. It:
 *   - loads the scene code only after the page has appeared (three.js is large)
 *   - keeps the canvas the same size as the hero
 *   - feeds scroll and pointer positions into the scene
 *   - stops drawing while the hero is off screen, to save battery
 *   - draws a single still frame when the person prefers reduced motion
 *
 * If WebGL is not available, the canvas stays invisible and the plain CSS
 * gradient underneath (`hero-fallback`) is what people see.
 */
export function HeroBackdrop({ trackRef }: HeroBackdropProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const reduceMotion = usePrefersReducedMotion()
  const [ready, setReady] = useState(false)

  useEffect(() => {
    const container = containerRef.current
    const canvas = canvasRef.current
    if (!container || !canvas) {
      return
    }

    // Set if this component goes away before the scene code has loaded.
    let cancelled = false
    let cleanUp = () => {}

    const mount = async () => {
      // `import()` downloads these files only now, not with the first page load.
      const [{ createHeroScene }, { createFrameLoop }] = await Promise.all([
        import('../../three/createHeroScene'),
        import('../../three/createFrameLoop'),
      ])
      if (cancelled) {
        return
      }

      let scene
      try {
        scene = createHeroScene(canvas)
      } catch {
        return // No WebGL: keep the CSS fallback.
      }

      const drawStill = () => {
        scene.setZoom(0)
        scene.renderFrame(STILL_FRAME_TIME)
      }

      // The pointer target is where the pointer is; `pointer` eases toward it.
      const pointerTarget = { x: 0, y: 0 }
      const pointer = { x: 0, y: 0 }

      const loop = createFrameLoop((time) => {
        pointer.x += (pointerTarget.x - pointer.x) * POINTER_EASING
        pointer.y += (pointerTarget.y - pointer.y) * POINTER_EASING
        scene.setPointer(pointer.x, pointer.y)
        scene.setZoom(trackProgress(trackRef.current, container.clientHeight))
        scene.renderFrame(time)
      })

      // Keep the drawing the same size as the hero, whatever the window does.
      const resizeObserver = new ResizeObserver(() => {
        scene.resize(container.clientWidth, container.clientHeight)
        if (reduceMotion) {
          drawStill()
        }
      })
      resizeObserver.observe(container)

      // Only animate while some part of the hero is visible.
      const visibilityObserver = new IntersectionObserver(([entry]) => {
        if (reduceMotion) {
          return
        }
        if (entry.isIntersecting) {
          loop.start()
        } else {
          loop.stop()
        }
      })
      visibilityObserver.observe(container)

      const onPointerMove = (event: PointerEvent) => {
        pointerTarget.x = (event.clientX / window.innerWidth) * 2 - 1
        pointerTarget.y = (event.clientY / window.innerHeight) * 2 - 1
      }
      if (!reduceMotion) {
        window.addEventListener('pointermove', onPointerMove, { passive: true })
      }

      scene.resize(container.clientWidth, container.clientHeight)
      drawStill()
      setReady(true)

      cleanUp = () => {
        loop.stop()
        resizeObserver.disconnect()
        visibilityObserver.disconnect()
        window.removeEventListener('pointermove', onPointerMove)
        scene.dispose()
      }
    }

    void mount()

    return () => {
      cancelled = true
      cleanUp()
    }
  }, [reduceMotion, trackRef])

  return (
    <div ref={containerRef} aria-hidden="true" className="hero-fallback absolute inset-0 -z-10">
      <canvas
        ref={canvasRef}
        className={`block size-full transition-opacity duration-[1400ms] ease-soft ${ready ? 'opacity-100' : 'opacity-0'}`}
      />
    </div>
  )
}
