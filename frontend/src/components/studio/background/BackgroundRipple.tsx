import { useEffect, useRef } from 'react'
import { onRippleRequest } from '../../../lib/rippleBus'

/**
 * The studio's background: a grid of dark squares that light up under the
 * pointer and send a ripple outward from a click.
 *
 * Based on Aceternity UI's "Background Ripple Effect"
 * (https://ui.aceternity.com/components/background-ripple-effect): the same
 * look, cell size, colors and ripple timing. Changes from the original:
 *
 *   - It is drawn on ONE <canvas> instead of ~500 separate boxes. The original
 *     rebuilt every box on each click and repainted their blurred shadows on
 *     every frame, which stuttered on a full-window grid. Here the still grid
 *     is drawn once into a hidden picture, and each frame copies that picture
 *     and paints only the cells that are lit. When nothing moves, nothing runs.
 *   - It covers the whole window and stays put while the page scrolls.
 *   - The studio's panels sit ON TOP, so it listens to the whole window and
 *     works out which cell is under the pointer. Clicks on buttons, links and
 *     fields never start a ripple.
 *   - Several ripples can overlap (click quickly and each one spreads).
 *   - Other parts of the studio can ask for a ripple (lib/rippleBus.ts): it
 *     ripples on its own while a model is thinking or the agents are at work.
 *   - With reduced motion on, there is no ripple (hover still lights a cell).
 */

const CELL = 56 // px, the size of one square
const BASE_ALPHA = 0.16 // how strongly the still grid shows
const LIT_STRENGTH = 0.4 // how strongly a lit cell (hover or ripple) shows, 1 = full
const FILL = '#171717'
const EDGE_GLOW = '#262626' // the soft lighter edge inside each cell
const BORDER = '#404040'
const LIT_FILL = '52 52 52' // a lit cell's fill (rgb)
const LIT_BORDER = '115 115 115' // a lit cell's border (rgb)

// The ripple's timing, as in the original: cells further away start later and last longer.
const DELAY_PER_CELL = 55 // ms
const BASE_DURATION = 200 // ms
const DURATION_PER_CELL = 80 // ms
const HOVER_FADE = 150 // ms for the cell under the pointer to light up or fade

/** Clicks on these never start a ripple: they belong to a control. */
const CONTROLS = 'button, a, input, textarea, select, label, summary, [role="tab"], [role="dialog"], [contenteditable="true"]'

type Ripple = { row: number; col: number; start: number }

/** How bright a cell is in a ripple at time `now`: 0 (still) up to 1 (fully lit). */
function rippleLight(ripple: Ripple, row: number, col: number, now: number): number {
  const distance = Math.hypot(ripple.row - row, ripple.col - col)
  const t = now - ripple.start - distance * DELAY_PER_CELL
  const duration = BASE_DURATION + distance * DURATION_PER_CELL
  if (t < 0 || t > duration) return 0
  const p = t / duration
  // Up quickly (the first 40%), then down slowly; eased so it never snaps.
  const raw = p < 0.4 ? p / 0.4 : 1 - (p - 0.4) / 0.6
  return raw * raw * (3 - 2 * raw)
}

/** When the last cell of this ripple goes dark again. */
function rippleEnd(ripple: Ripple, rows: number, cols: number): number {
  const far = Math.max(
    Math.hypot(ripple.row, ripple.col),
    Math.hypot(ripple.row, cols - ripple.col),
    Math.hypot(rows - ripple.row, ripple.col),
    Math.hypot(rows - ripple.row, cols - ripple.col),
  )
  return ripple.start + far * (DELAY_PER_CELL + DURATION_PER_CELL) + BASE_DURATION
}

export function BackgroundRipple() {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    const context = canvas?.getContext('2d')
    if (!canvas || !context) return

    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)')
    let rows = 0
    let cols = 0
    let base: HTMLCanvasElement | null = null // the still grid, drawn once per window size
    let ripples: Ripple[] = []
    let hovered: number | null = null // index of the cell under the pointer
    const hoverLight = new Map<number, number>() // cells fading in or out, 0..1
    let frame = 0
    let lastFrame = 0

    // Draw the still grid once, into a hidden canvas the size of the window.
    const buildBase = () => {
      const ratio = window.devicePixelRatio || 1
      cols = Math.ceil(window.innerWidth / CELL) + 1
      rows = Math.ceil(window.innerHeight / CELL) + 1
      canvas.width = Math.round(window.innerWidth * ratio)
      canvas.height = Math.round(window.innerHeight * ratio)
      canvas.style.width = `${window.innerWidth}px`
      canvas.style.height = `${window.innerHeight}px`

      base = document.createElement('canvas')
      base.width = canvas.width
      base.height = canvas.height
      const b = base.getContext('2d')
      if (!b) return
      b.scale(ratio, ratio)
      b.globalAlpha = BASE_ALPHA
      for (let row = 0; row < rows; row++) {
        for (let col = 0; col < cols; col++) {
          const x = col * CELL
          const y = row * CELL
          // Dark middle, slightly lighter edges: the original's inset glow.
          const glow = b.createRadialGradient(x + CELL / 2, y + CELL / 2, CELL * 0.15, x + CELL / 2, y + CELL / 2, CELL * 0.75)
          glow.addColorStop(0, FILL)
          glow.addColorStop(1, EDGE_GLOW)
          b.fillStyle = glow
          b.fillRect(x, y, CELL, CELL)
          b.strokeStyle = BORDER
          b.lineWidth = 0.5
          b.strokeRect(x + 0.25, y + 0.25, CELL - 0.5, CELL - 0.5)
        }
      }
    }

    // One frame: the still grid, then every lit cell on top of it.
    const draw = (now: number) => {
      frame = 0
      const ratio = window.devicePixelRatio || 1
      const step = lastFrame ? now - lastFrame : 16
      lastFrame = now
      context.setTransform(1, 0, 0, 1, 0, 0)
      context.clearRect(0, 0, canvas.width, canvas.height)
      if (base) context.drawImage(base, 0, 0)
      context.setTransform(ratio, 0, 0, ratio, 0, 0)

      // Hover: ease the cell under the pointer up, and the others back down.
      if (hovered !== null && !hoverLight.has(hovered)) hoverLight.set(hovered, 0)
      for (const [index, value] of hoverLight) {
        const target = index === hovered ? 1 : 0
        const next = target > value ? Math.min(1, value + step / HOVER_FADE) : Math.max(0, value - step / HOVER_FADE)
        if (next === 0 && target === 0) hoverLight.delete(index)
        else hoverLight.set(index, next)
      }

      ripples = ripples.filter((ripple) => now < rippleEnd(ripple, rows, cols))
      const lit = new Map<number, number>()
      for (const [index, value] of hoverLight) lit.set(index, value * 0.6)
      for (const ripple of ripples) {
        // Only the cells the wave can have reached so far are checked.
        const reach = (now - ripple.start) / DELAY_PER_CELL
        const top = Math.max(0, Math.floor(ripple.row - reach))
        const bottom = Math.min(rows - 1, Math.ceil(ripple.row + reach))
        const left = Math.max(0, Math.floor(ripple.col - reach))
        const right = Math.min(cols - 1, Math.ceil(ripple.col + reach))
        for (let row = top; row <= bottom; row++) {
          for (let col = left; col <= right; col++) {
            const light = rippleLight(ripple, row, col, now)
            if (light > 0) {
              const index = row * cols + col
              lit.set(index, Math.max(lit.get(index) ?? 0, light))
            }
          }
        }
      }

      context.lineWidth = 0.5
      for (const [index, litAmount] of lit) {
        const light = litAmount * LIT_STRENGTH
        const x = (index % cols) * CELL
        const y = Math.floor(index / cols) * CELL
        context.fillStyle = `rgb(${LIT_FILL} / ${light})`
        context.fillRect(x, y, CELL, CELL)
        context.strokeStyle = `rgb(${LIT_BORDER} / ${light})`
        context.strokeRect(x + 0.25, y + 0.25, CELL - 0.5, CELL - 0.5)
      }

      // Keep going only while something is still moving.
      if (ripples.length > 0 || hoverLight.size > 0) request()
      else lastFrame = 0
    }

    const request = () => {
      if (!frame) frame = requestAnimationFrame(draw)
    }

    const cellAt = (x: number, y: number) => {
      const col = Math.floor(x / CELL)
      const row = Math.floor(y / CELL)
      return row >= 0 && col >= 0 && row < rows && col < cols ? { row, col } : null
    }

    const onMove = (event: PointerEvent) => {
      const cell = cellAt(event.clientX, event.clientY)
      const index = cell ? cell.row * cols + cell.col : null
      if (index !== hovered) {
        hovered = index
        request()
      }
    }

    const onLeave = () => {
      hovered = null
      request()
    }

    const onClick = (event: MouseEvent) => {
      if (reducedMotion.matches) return
      if ((event.target as Element | null)?.closest(CONTROLS)) return
      if (window.getSelection()?.toString()) return // the user was selecting text
      const cell = cellAt(event.clientX, event.clientY)
      if (!cell) return
      ripples.push({ ...cell, start: performance.now() })
      request()
    }

    const onResize = () => {
      buildBase()
      request()
    }

    // A ripple asked for by the studio (a model thinking, the agents at work).
    const stopListening = onRippleRequest((x, y) => {
      if (reducedMotion.matches) return
      const cell = cellAt(x, y)
      if (!cell) return
      ripples.push({ ...cell, start: performance.now() })
      request()
    })

    buildBase()
    request()
    window.addEventListener('pointermove', onMove, { passive: true })
    document.documentElement.addEventListener('pointerleave', onLeave)
    window.addEventListener('click', onClick)
    window.addEventListener('resize', onResize)
    return () => {
      window.removeEventListener('pointermove', onMove)
      document.documentElement.removeEventListener('pointerleave', onLeave)
      window.removeEventListener('click', onClick)
      window.removeEventListener('resize', onResize)
      stopListening()
      cancelAnimationFrame(frame)
    }
  }, [])

  return <canvas ref={canvasRef} aria-hidden="true" className="pointer-events-none fixed inset-0 z-0" />
}
