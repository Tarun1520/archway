import { useReducedMotion } from 'motion/react'
import { useCallback, useEffect, useRef, useState } from 'react'
import type { ReactNode, RefObject } from 'react'
import { createPortal } from 'react-dom'
import type { ArchyAction } from '../../../content/archy'
import { archyUi } from '../../../content/archy'
import { ArchyBubble } from './ArchyBubble'
import { ArchyPortal } from './ArchyPortal'
import { createArchyStage, type ArchyStage, type RobotScreen } from './three/archyStage'

interface ArchyStage3DProps {
  /** Out of the portal (true) or away (false). */
  awake: boolean
  /** The gesture that goes with what Archy is saying. */
  action: ArchyAction
  /** How loud the microphone is while listening. */
  micLevel: number
  /** Whether he plays tricks in the air (skydiving, flips ...) when he has nothing to say. */
  tricks: boolean
  /**
   * True on a wide screen: Archy's stage is a canvas along the bottom of the
   * window, and this component only reserves the space for his portal (he floats up out of it).
   * False (the phone-sized drawer): the stage fills this component.
   */
  strip: boolean
  /** The height this component takes in the sidebar. */
  height: number
  /** What he is saying, as a speech bubble coming out of him. */
  bubble: { text: string; visible: boolean; problem: boolean }
  /** Clicking Archy himself sends him back to the portal. */
  onBack: () => void
  /** Drawn over the portal: its click target and the invitation. */
  children?: ReactNode
  className?: string
}

/**
 * Archy and his portal, in 3D (three/archyStage.ts does the drawing).
 *
 * Two layouts (see the stage's own notes):
 *   dock   the canvas fills this component. Used in the narrow drawer.
 *   strip  this component is only a placeholder in the sidebar; the canvas is
 *          a fixed strip along the bottom of the whole window (made with a
 *          portal, so no parent can clip it or move it), clicks go through it
 *          except on Archy himself, and the portal is drawn exactly over the
 *          placeholder.
 *
 * Where WebGL is not available, the flat portal is shown instead.
 */
export function ArchyStage3D(props: ArchyStage3DProps) {
  const { strip, height, className = '', children } = props
  const placeholder = useRef<HTMLDivElement>(null)
  const [failed, setFailed] = useState(false)
  const fail = useCallback(() => setFailed(true), []) // one steady function, so the stage is not rebuilt on every redraw

  return (
    <div ref={placeholder} className={`relative w-full shrink-0 ${className}`} style={{ height }}>
      {failed ? (
        <ArchyPortal active={props.awake} className="absolute inset-x-0 bottom-0 w-full" />
      ) : strip ? (
        <StripStage {...props} placeholder={placeholder} onFailed={fail} />
      ) : (
        <DockStage {...props} onFailed={fail} />
      )}
      {children}
    </div>
  )
}

/** Keeps the stage told about the three things that change, and the roaming switch. */
function useStageInputs(stage: RefObject<ArchyStage | null>, { awake, action, micLevel, tricks }: ArchyStage3DProps) {
  useEffect(() => stage.current?.setAwake(awake), [stage, awake])
  useEffect(() => stage.current?.setAction(action), [stage, action])
  useEffect(() => stage.current?.setMicLevel(micLevel), [stage, micLevel])
  useEffect(() => stage.current?.setTricks(tricks), [stage, tricks])
}

/** The stage fills its box (the narrow drawer). */
function DockStage(props: ArchyStage3DProps & { onFailed: () => void }) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const stage = useRef<ArchyStage | null>(null)
  const reduceMotion = useReducedMotion() ?? false
  const latest = useRef(props)
  latest.current = props
  const { onFailed } = props

  useEffect(() => {
    const element = canvas.current
    const box = element?.parentElement
    if (!element || !box) return
    let created: ArchyStage
    try {
      created = createArchyStage(element, { reducedMotion: reduceMotion })
    } catch {
      onFailed()
      return
    }
    stage.current = created
    created.setAwake(latest.current.awake)
    created.setAction(latest.current.action)
    created.setTricks(latest.current.tricks)
    const resize = () => created.resize(box.clientWidth, box.clientHeight)
    resize()
    const sizeWatcher = new ResizeObserver(resize)
    sizeWatcher.observe(box)
    const viewWatcher = new IntersectionObserver(([entry]) => created.setVisible(entry.isIntersecting))
    viewWatcher.observe(box)
    return () => {
      sizeWatcher.disconnect()
      viewWatcher.disconnect()
      created.dispose()
      stage.current = null
    }
  }, [reduceMotion, onFailed])

  useStageInputs(stage, props)
  return (
    <>
      <canvas ref={canvas} aria-hidden="true" className="absolute inset-0 block h-full w-full" />
      {/* The bubble sits at the top of his stage, its tail pointing down at him. */}
      <div className="absolute inset-x-0 top-0 flex justify-center">
        <ArchyBubble {...props.bubble} inline />
      </div>
      {/* In the narrow drawer he stands on his portal: the ripples start from the middle of the stage. */}
      <div data-ripple-anchor="archy" aria-hidden="true" className="pointer-events-none absolute top-[55%] left-1/2 size-px" />
    </>
  )
}

/** The stage is a strip along the bottom of the window; the portal sits over the placeholder. */
function StripStage(props: ArchyStage3DProps & { placeholder: RefObject<HTMLDivElement | null>; onFailed: () => void }) {
  const { placeholder, onFailed, onBack } = props
  const container = useRef<HTMLDivElement>(null)
  const canvas = useRef<HTMLCanvasElement>(null)
  const hit = useRef<HTMLButtonElement>(null)
  const anchor = useRef<HTMLDivElement>(null)
  const bubbleBox = useRef<HTMLDivElement>(null)
  const stage = useRef<ArchyStage | null>(null)
  const reduceMotion = useReducedMotion() ?? false
  const latest = useRef(props)
  latest.current = props

  useEffect(() => {
    const element = canvas.current
    const strip = container.current
    const target = placeholder.current
    if (!element || !strip || !target) return
    let created: ArchyStage
    try {
      created = createArchyStage(element, {
        reducedMotion: reduceMotion,
        // Puts the click target on Archy, every frame (no React update needed).
        onRobot: (robot: RobotScreen) => {
          // The ripple anchor sits in the middle of his body: ripples start from behind him.
          if (anchor.current) anchor.current.style.transform = `translate(${robot.x}px, ${robot.y - robot.height / 2}px)`
          // The speech bubble rides above his head, kept inside the window; its tail points at him.
          const bubble = bubbleBox.current
          const text = bubble?.firstElementChild as HTMLElement | null
          if (bubble && text) {
            const margin = 8
            const width = text.offsetWidth
            const left = Math.min(Math.max(robot.x - width / 2, margin), strip.clientWidth - width - margin)
            bubble.style.transform = `translate(${left}px, ${robot.y - robot.height - text.offsetHeight - 12}px)`
            bubble.style.setProperty('--tail-x', `${Math.min(Math.max(robot.x - left, 16), Math.max(16, width - 16))}px`)
          }
          const button = hit.current
          if (!button) return
          const show = robot.visible && latest.current.awake
          button.style.visibility = show ? 'visible' : 'hidden'
          button.tabIndex = show ? 0 : -1
          const width = Math.max(56, robot.height * 0.62)
          button.style.width = `${width}px`
          button.style.height = `${robot.height}px`
          button.style.transform = `translate(${robot.x - width / 2}px, ${robot.y - robot.height}px)`
        },
      })
    } catch {
      onFailed()
      return
    }
    stage.current = created
    created.setAwake(latest.current.awake)
    created.setAction(latest.current.action)
    created.setTricks(latest.current.tricks)

    // The strip starts a little above the portal (room for his head and the beam) and runs to the window's bottom.
    let frame = 0
    const measure = () => {
      frame = 0
      const box = target.getBoundingClientRect()
      if (box.width === 0) return
      const unit = Math.min(104, Math.max(70, (box.width * 0.84) / 2.12))
      const portalY = box.bottom - 36 // leaves room above the portal for the invitation, so the two never touch
      const top = Math.max(0, Math.round(portalY - 2.6 * unit))
      const height = Math.max(120, window.innerHeight - top)
      strip.style.height = `${height}px`
      created.resize(strip.clientWidth, height)
      created.setPlacement({ x: box.left + box.width / 2, y: portalY - top, scale: unit })
    }
    const schedule = () => {
      if (!frame) frame = requestAnimationFrame(measure)
    }
    measure()
    const sizeWatcher = new ResizeObserver(schedule)
    sizeWatcher.observe(target)
    window.addEventListener('resize', schedule)
    window.addEventListener('scroll', schedule, { passive: true })
    return () => {
      cancelAnimationFrame(frame)
      sizeWatcher.disconnect()
      window.removeEventListener('resize', schedule)
      window.removeEventListener('scroll', schedule)
      created.dispose()
      stage.current = null
    }
  }, [reduceMotion, placeholder, onFailed])

  useStageInputs(stage, props)

  return createPortal(
    <div ref={container} className="pointer-events-none fixed inset-x-0 bottom-0 z-[35]">
      <canvas ref={canvas} aria-hidden="true" className="block h-full w-full" />
      {/* An invisible button that follows Archy: clicking him sends him back to the portal. */}
      <button
        ref={hit}
        type="button"
        onClick={onBack}
        aria-label={archyUi.sendBack}
        title={archyUi.sendBack}
        style={{ visibility: 'hidden' }}
        className="pointer-events-auto absolute top-0 left-0 cursor-pointer rounded-pill focus-visible:outline-2 focus-visible:outline-vermilion"
      />
      <ArchyBubble ref={bubbleBox} {...props.bubble} />
      {/* A point in the middle of his body, where the background ripples start while he speaks (hooks/useRippleWhile.ts). */}
      <div ref={anchor} data-ripple-anchor="archy" aria-hidden="true" className="pointer-events-none absolute top-0 left-0 size-px" />
    </div>,
    document.body,
  )
}
