import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useCurtain } from '../../../hooks/useCurtain'
import { studioAgentsCopy } from '../../../content/studio'
import { AGENTS, type AgentId, type TeamPicture } from '../../../lib/agentTeam'
import { AgentStage2D } from './AgentStage2D'
import { GREETINGS } from './three/greetings'
import { createTeamStage, NAME_ABOVE, type Rect, type TeamStage } from './three/teamStage'


/**
 * The agents as 3D robots (three/teamStage.ts does the drawing). This wrapper
 * gives it a canvas, keeps it the right size, pauses it while it is off
 * screen, feeds it the team picture, and draws the name labels as plain HTML
 * under each robot's feet (so they stay crisp and screen readers can read them).
 *
 * Pointing at a robot (or its name) makes it greet you: the stage plays its
 * move, and this wrapper shows what it says in a speech bubble over its head.
 *
 * The robots are drawn on a layer over the WHOLE WINDOW (a canvas portalled to
 * the page body, with no pointer events), lined up with this panel, so that
 * when they come on or go off they really cross the screen instead of
 * vanishing at the panel's edge. Pointer events are read on the panel itself.
 *
 * The entrance waits until the page can be seen: not under the welcome film,
 * and with the panel on screen.
 *
 * Where WebGL is not available, it shows the flat robots instead.
 */

/** The panel's rectangle cut down by every scrolling box around it (the part that can actually be seen). */
function visiblePart(element: HTMLElement, box: Rect): Rect {
  let left = box.x
  let top = box.y
  let right = box.x + box.width
  let bottom = box.y + box.height
  for (let parent = element.parentElement; parent; parent = parent.parentElement) {
    const style = getComputedStyle(parent)
    if (/(auto|scroll|hidden|clip)/.test(style.overflowX + style.overflowY)) {
      const r = parent.getBoundingClientRect()
      left = Math.max(left, r.left)
      top = Math.max(top, r.top)
      right = Math.min(right, r.right)
      bottom = Math.min(bottom, r.bottom)
    }
  }
  return { x: left, y: top, width: Math.max(0, right - left), height: Math.max(0, bottom - top) }
}
interface AgentStage3DProps {
  team: TeamPicture
  height?: number
  /** Play the robots' entrance when the stage is created (each comes on in its own way). */
  entrance?: boolean
  onEntered?: () => void
  /** Set to true to make every robot leave the stage; `onLeft` is called once they are all gone. */
  leaving?: boolean
  onLeft?: () => void
  /** Set to true to make every robot greet at once (a visit's wave). */
  wave?: boolean
}

/** If the stage cannot show the exit (hidden, paused), the page still moves on after this long. */
const EXIT_FALLBACK_MS = 3200

export function AgentStage3D({ team, height = 300, entrance = false, onEntered, leaving = false, onLeft, wave = false }: AgentStage3DProps) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const stageRef = useRef<TeamStage | null>(null)
  const labelRefs = useRef<Partial<Record<AgentId, HTMLDivElement | null>>>({})
  const bubbleRef = useRef<HTMLDivElement>(null)
  const overlayRef = useRef<HTMLDivElement>(null)
  const leadAnchorRef = useRef<HTMLDivElement>(null)
  const heads = useRef<Partial<Record<AgentId, { x: number; headY: number }>>>({})
  const [failed, setFailed] = useState(false)
  const [greeting, setGreeting] = useState<AgentId | null>(null)
  const greetingRef = useRef<AgentId | null>(null)
  const [pointing, setPointing] = useState(false)
  const reduceMotion = useReducedMotion() ?? false
  const teamRef = useRef(team)
  teamRef.current = team
  const entranceRef = useRef({ entrance, onEntered })
  entranceRef.current = { entrance, onEntered }
  const covered = useCurtain()
  const [inView, setInView] = useState(false)
  const [entrancePending, setEntrancePending] = useState(false)

  // Keeps the speech bubble over the greeting robot's head.
  // Keeps the speech bubble over the greeting robot's head, but always fully
  // inside the stage: near an edge the bubble slides inward and its tail
  // (--tail-x) still points at the robot.
  const placeBubble = () => {
    const id = greetingRef.current
    const head = id ? heads.current[id] : undefined
    const holder = bubbleRef.current
    const bubble = holder?.firstElementChild as HTMLElement | null
    const stage = wrapRef.current
    if (!holder || !bubble || !stage || !head) return
    const margin = 6
    const width = bubble.offsetWidth
    const height = bubble.offsetHeight
    const left = Math.min(Math.max(head.x - width / 2, margin), stage.clientWidth - width - margin)
    const nameTop = id && NAME_ABOVE.has(id) ? labelTops.current[id] : undefined
    const top = Math.max((nameTop ?? head.headY) - 8 - height, margin)
    holder.style.transform = `translate(${left}px, ${top}px)`
    holder.style.setProperty('--tail-x', `${Math.min(Math.max(head.x - left, 16), width - 16)}px`)
  }

  /**
   * Puts each name where it can be read: ABOVE the head for the back row
   * (NAME_ABOVE: their feet are behind the front robots) and under the feet
   * for the rest. Every name is kept inside the stage, and moved just enough
   * (up for names above, down for names below) when it would touch another.
   * Each name also has a dark pill behind it, so it reads anywhere.
   */
  const labelTops = useRef<Partial<Record<AgentId, number>>>({})
  const placeLabels = (positions: Record<AgentId, { x: number; y: number; headY: number; hidden: boolean }>) => {
    const width = wrapRef.current?.clientWidth ?? 0
    const gap = 3
    const placed: { left: number; top: number; right: number; bottom: number }[] = []
    const touching = (left: number, top: number, w: number, h: number) =>
      placed.find((o) => left < o.right + gap && left + w > o.left - gap && top < o.bottom + gap && top + h > o.top - gap)

    // Names above heads first (highest on screen first), then names under feet.
    const above = AGENTS.filter((a) => NAME_ABOVE.has(a.id)).sort((a, b) => positions[a.id].headY - positions[b.id].headY)
    const below = AGENTS.filter((a) => !NAME_ABOVE.has(a.id)).sort((a, b) => positions[a.id].y - positions[b.id].y)
    for (const agent of [...above, ...below]) {
      const label = labelRefs.current[agent.id]
      if (!label) continue
      label.style.visibility = positions[agent.id].hidden ? 'hidden' : 'visible'
      if (positions[agent.id].hidden) continue
      const w = label.offsetWidth
      const h = label.offsetHeight
      const at = positions[agent.id]
      const up = NAME_ABOVE.has(agent.id)
      const left = Math.min(Math.max(at.x - w / 2, 2), width - w - 2)
      let top = up ? at.headY - h - 4 : at.y + 3
      for (let other = touching(left, top, w, h); other; other = touching(left, top, w, h)) {
        top = up ? other.top - gap - h : other.bottom + gap
      }
      top = Math.max(top, 2)
      placed.push({ left, top, right: left + w, bottom: top + h })
      labelTops.current[agent.id] = top
      label.style.transform = `translate(${left}px, ${top}px)`
    }
  }

  // Create the stage once, and keep it sized and paused when hidden.
  useEffect(() => {
    const canvas = canvasRef.current
    const wrap = wrapRef.current
    if (!canvas || !wrap) return
    let stage: TeamStage
    try {
      stage = createTeamStage(canvas, {
        reducedMotion: reduceMotion,
        onLabels: (positions) => {
          for (const agent of AGENTS) heads.current[agent.id] = { x: positions[agent.id].x, headY: positions[agent.id].headY }
          placeLabels(positions)
          // The lead's middle: where the "agents at work" ripples start (hooks/useRippleWhile.ts).
          const lead = positions.lead
          if (leadAnchorRef.current) leadAnchorRef.current.style.transform = `translate(${lead.x}px, ${(lead.y + lead.headY) / 2}px)`
          placeBubble()
        },
        onGreeting: (id) => {
          greetingRef.current = id
          setGreeting(id)
        },
      })
    } catch {
      setFailed(true)
      return
    }
    stageRef.current = stage
    stage.update(teamRef.current) // show the team as it is right now
    stage.setHuddle(teamRef.current.designing)
    if (entranceRef.current.entrance && !reduceMotion) {
      stage.hide() // off stage until the page can be seen; then each comes on in its own way
      setEntrancePending(true)
    }
    // Lines the whole-window layer up with this panel: on resize, on scroll (of the page or any box around it).
    let measuring = 0
    const measure = () => {
      measuring = 0
      const r = wrap.getBoundingClientRect()
      const box = { x: r.left, y: r.top, width: r.width, height: r.height }
      stage.place(box, visiblePart(wrap, box), window.innerWidth, window.innerHeight)
      // The names and the speech bubble sit on their own layer, just above the robots, lined up with the panel.
      const overlay = overlayRef.current
      if (overlay) {
        overlay.style.display = r.width === 0 ? 'none' : 'block'
        overlay.style.left = `${r.left}px`
        overlay.style.top = `${r.top}px`
        overlay.style.width = `${r.width}px`
        overlay.style.height = `${r.height}px`
      }
    }
    const schedule = () => {
      if (!measuring) measuring = requestAnimationFrame(measure)
    }
    measure()
    const sizeWatcher = new ResizeObserver(schedule)
    sizeWatcher.observe(wrap)
    window.addEventListener('resize', schedule)
    window.addEventListener('scroll', schedule, { capture: true, passive: true })
    const viewWatcher = new IntersectionObserver(([entry]) => {
      stage.setVisible(entry.isIntersecting)
      setInView(entry.isIntersecting)
    })
    viewWatcher.observe(wrap)
    return () => {
      cancelAnimationFrame(measuring)
      sizeWatcher.disconnect()
      window.removeEventListener('resize', schedule)
      window.removeEventListener('scroll', schedule, { capture: true })
      viewWatcher.disconnect()
      stage.dispose()
      stageRef.current = null
    }
  }, [reduceMotion])

  // Every new team picture (a robot started, a message was sent) goes to the stage.
  useEffect(() => {
    stageRef.current?.update(team)
  }, [team])

  // The entrance plays once the page can be seen: the film has lifted and the panel is on screen.
  useEffect(() => {
    if (!entrancePending || covered || !inView) return
    const start = window.setTimeout(() => {
      stageRef.current?.enter() // each robot comes on in its own way
      entranceRef.current.onEntered?.()
      setEntrancePending(false)
    }, 250) // a beat after the page appears, so the arrival is seen from its start
    return () => window.clearTimeout(start)
  }, [entrancePending, covered, inView])

  useEffect(() => {
    if (wave) stageRef.current?.waveAll()
  }, [wave])

  // While the options are drafted, the team gathers round the lead.
  useEffect(() => {
    stageRef.current?.setHuddle(team.designing)
  }, [team.designing])

  // Leaving: every robot goes off in its own way, then the page is told (or after a fallback, if it cannot show it).
  const onLeftRef = useRef(onLeft)
  onLeftRef.current = onLeft
  useEffect(() => {
    if (!leaving) return
    let done = false
    const finish = () => {
      if (done) return
      done = true
      onLeftRef.current?.()
    }
    const fallback = window.setTimeout(finish, EXIT_FALLBACK_MS)
    void (stageRef.current?.exit() ?? Promise.resolve()).then(finish)
    return () => window.clearTimeout(fallback)
  }, [leaving])

  // The bubble is placed as soon as it appears (the stage then keeps it in place).
  useEffect(() => {
    placeBubble()
    const frame = requestAnimationFrame(placeBubble)
    return () => cancelAnimationFrame(frame)
  }, [greeting])

  if (failed) return <AgentStage2D team={team} />

  const onPointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    const box = event.currentTarget.getBoundingClientRect()
    const over = stageRef.current?.pointAt(event.clientX - box.left, event.clientY - box.top) ?? null
    setPointing(over !== null)
  }

  return (
    <div
      ref={wrapRef}
      onPointerMove={onPointerMove}
      onPointerLeave={() => {
        stageRef.current?.pointAt(null, null)
        setPointing(false)
      }}
      className={`relative w-full overflow-hidden ${pointing ? 'cursor-pointer' : ''}`}
      style={{ height }}
    >
      {/* The robots' layer covers the whole window (no pointer events), lined up with this panel. */}
      {createPortal(<canvas ref={canvasRef} aria-hidden="true" className="pointer-events-none fixed inset-0 z-[45] block h-full w-full" />, document.body)}

      {/*
        The names and the speech bubble. The robots are drawn on a layer over the whole window
        (z 45), so anything left inside the panel would be hidden whenever a robot stands in
        front of it. They get a layer of their own just above (z 46), kept lined up with the
        panel; positions inside it are the panel's own coordinates.
      */}
      {createPortal(
        <div ref={overlayRef} className="pointer-events-none fixed z-[46] overflow-hidden" style={{ display: 'none' }}>
      {AGENTS.map((a) => {
        const agent = team.agents[a.id]
        const lead = a.id === 'lead'
        return (
          <div
            key={a.id}
            ref={(element) => {
              labelRefs.current[a.id] = element
            }}
            role="img"
            aria-label={`${a.label}: ${agent.doing ?? studioAgentsCopy.status[agent.status]}`}
            title={`${a.role}. ${agent.doing ?? studioAgentsCopy.status[agent.status]}`}
            onPointerEnter={() => stageRef.current?.greet(a.id)}
            className={`pointer-events-auto absolute top-0 left-0 cursor-default rounded-pill bg-void/75 px-6 py-[1px] font-code text-[10px] whitespace-nowrap uppercase tracking-[0.1em] backdrop-blur-[2px] ${
              lead ? 'text-vermilion' : agent.status === 'working' ? 'text-chalk' : 'text-ash'
            }`}
          >
            {a.label}
            {a.id === 'scout' && agent.copies > 1 ? ` ×${agent.copies}` : ''}
          </div>
        )
      })}

      {/* An invisible point at the lead's middle, for the "agents at work" ripples. */}
      <div ref={leadAnchorRef} data-ripple-anchor="lead" aria-hidden="true" className="pointer-events-none absolute top-0 left-0 size-px" />

      {/* What the greeting robot says. */}
      <div ref={bubbleRef} className="pointer-events-none absolute top-0 left-0">
        <AnimatePresence>
          {greeting && (
            <motion.p
              key={greeting}
              role="status"
              initial={reduceMotion ? false : { opacity: 0, y: 6, scale: 0.9 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, transition: { duration: 0.15 } }}
              transition={{ type: 'spring', stiffness: 420, damping: 26 }}
              className="relative w-max max-w-[220px] rounded-[14px] bg-chalk px-12 py-8 text-center text-[13px] leading-[1.35] font-medium text-void shadow-[0_8px_24px_-8px_rgba(0,0,0,0.6)]"
            >
              {GREETINGS[greeting].line}
              <span aria-hidden="true" className="absolute -bottom-[5px] left-[var(--tail-x,50%)] size-10 -translate-x-1/2 rotate-45 bg-chalk" />
            </motion.p>
          )}
        </AnimatePresence>
      </div>
        </div>,
        document.body,
      )}
    </div>
  )
}
