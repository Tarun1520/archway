import { useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useCurtain } from '../../../hooks/useCurtain'
import { teamFromEvents } from '../../../lib/agentTeam'
import { AgentStage3D } from './AgentStage3D'
import { ARRIVALS, totalTime } from './three/teamActs'

/** How long the team waves before it heads off again, in milliseconds. */
const WAVE_MS = 2600

interface Spot {
  x: number
  y: number
  width: number
  height: number
}

/** Media and controls: a point on one of them is never free space. */
const SOLID = 'img, svg, canvas, video, button, input, textarea, select, a, table, pre, code, iframe'

/** Is the point over text that is drawn (a text node of this element, not just the element's box)? */
function onText(element: Element, x: number, y: number): boolean {
  for (const node of element.childNodes) {
    if (node.nodeType !== Node.TEXT_NODE || !node.textContent?.trim()) continue
    const range = document.createRange()
    range.selectNodeContents(node)
    for (const r of range.getClientRects()) {
      if (x >= r.left - 8 && x <= r.right + 8 && y >= r.top - 8 && y <= r.bottom + 8) return true
    }
  }
  return false
}

/** Does this element paint something of its own (a background or a border), like a card? */
function paints(element: Element): boolean {
  const style = getComputedStyle(element)
  const alpha = style.backgroundColor.match(/rgba?\(([^)]+)\)/)?.[1].split(',')[3]
  const background = style.backgroundColor !== 'transparent' && (alpha === undefined || Number(alpha) > 0.05)
  const border = ['Top', 'Right', 'Bottom', 'Left'].some((side) => parseFloat(style.getPropertyValue(`border-${side.toLowerCase()}-width`)) > 0)
  return background || border || style.backgroundImage !== 'none'
}

/**
 * Is the page empty at this point? Not if what is drawn there is text, a picture or a control, or a box that paints
 * its own background or border (a card), up to the first large container (the page's own panels, which are the
 * background here). The empty part of a heading's box, beside its words, IS free space.
 * (Layers with no pointer events, such as the robots' own canvas and the background grid, are not "on top" here.)
 */
function emptyAt(x: number, y: number): boolean {
  const element = document.elementFromPoint(x, y)
  if (!element || element === document.body || element === document.documentElement) return true
  if (element.closest(SOLID) || onText(element, x, y)) return false
  const large = 0.2 * window.innerWidth * window.innerHeight
  for (let box: Element | null = element; box && box !== document.body; box = box.parentElement) {
    const r = box.getBoundingClientRect()
    if (r.width * r.height >= large) break
    if (paints(box)) return false
  }
  return true
}

function emptyRect(x: number, y: number, width: number, height: number): boolean {
  for (let row = 0; row <= 3; row++) {
    for (let column = 0; column <= 4; column++) {
      if (!emptyAt(x + 4 + (column / 4) * (width - 8), y + 4 + (row / 3) * (height - 8))) return false
    }
  }
  return true
}

/**
 * Where there is room on the page right now: the first spot, from the top right, where nothing is drawn but the
 * page itself (tried at three sizes, largest first). Null when the page has no room anywhere.
 */
function freeSpot(): Spot | null {
  const top = (document.querySelector('header')?.getBoundingClientRect().bottom ?? 80) + 12
  const left = (document.querySelector('aside')?.getBoundingClientRect().right ?? 0) + 12
  for (const [width, height] of [[480, 300], [520, 240], [400, 260], [520, 190], [360, 200]]) {
    for (let y = top; y + height <= window.innerHeight - 12; y += 32) {
      for (let x = window.innerWidth - width - 20; x >= left; x -= 32) {
        if (emptyRect(x, y, width, height)) return { x, y, width, height }
      }
    }
  }
  return null
}

/**
 * The team's visit, on a page where the agents are not needed (they have no panel there): when the person opens the
 * workspace, the robots come onto a free spot of the page (found by looking at what is drawn where, freeSpot), each in its own way, wave together (each with its own
 * greeting), and head off again, each in its own way. Then this is gone. Nothing here can be clicked.
 *
 *   arriving -> waving -> leaving -> onDone()
 */
export function AgentsVisit({ onDone }: { onDone: () => void }) {
  // The free spot is found once the page has settled and can be seen (not under the welcome film); no room, no visit.
  const covered = useCurtain()
  const [spot, setSpot] = useState<Spot | null>(null)
  const onDoneRef = useRef(onDone)
  onDoneRef.current = onDone
  useEffect(() => {
    if (covered || spot) return
    const look = window.setTimeout(() => {
      const found = freeSpot()
      if (found) setSpot(found)
      else onDoneRef.current()
    }, 450)
    return () => window.clearTimeout(look)
  }, [covered, spot])
  const [phase, setPhase] = useState<'arriving' | 'waving' | 'leaving'>('arriving')
  const team = useMemo(() => teamFromEvents([]), []) // everyone at rest: they are only saying hello

  // The arrival starts when the stage says so (after the welcome film has lifted); waving starts once all are in.
  const [arrived, setArrived] = useState(false)
  useEffect(() => {
    if (!arrived) return
    const wave = window.setTimeout(() => setPhase('waving'), totalTime(ARRIVALS) * 1000 + 150)
    return () => window.clearTimeout(wave)
  }, [arrived])
  useEffect(() => {
    if (phase !== 'waving') return
    const leave = window.setTimeout(() => setPhase('leaving'), WAVE_MS)
    return () => window.clearTimeout(leave)
  }, [phase])

  if (!spot) return null
  return createPortal(
    <div
      aria-hidden="true"
      className="pointer-events-none fixed z-[44]"
      style={{ left: spot.x, top: spot.y, width: spot.width, height: spot.height }}
    >
      <AgentStage3D
        team={team}
        height={spot.height}
        entrance
        onEntered={() => setArrived(true)}
        wave={phase === 'waving'}
        leaving={phase === 'leaving'}
        onLeft={onDone}
      />
    </div>,
    document.body,
  )
}
