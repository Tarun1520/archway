import { CanvasTexture, SRGBColorSpace } from 'three'

/**
 * The code that runs on a robot's visor while its agent works.
 *
 * A small canvas is painted with lines of made-up code that scroll upward, and
 * used as the picture on a thin layer over the visor (buildRobot.ts). It is
 * only drawn while the agent works (teamStage.ts calls `tick`), so a quiet
 * team costs nothing. The code is decoration: generic lines, never anything
 * the agent really read or wrote.
 */

const WIDTH = 256
const HEIGHT = 150
const LINE = 22 // px between lines
const VISIBLE = Math.ceil(HEIGHT / LINE) + 2
const STEP_SECONDS = 0.16 // a new line appears this often

/** Plain, generic statements, so the screen reads as "something is being worked out". */
const SNIPPETS = [
  'for (const item of rows) {',
  'if (item.ok) keep(item)',
  'score += weigh(item)',
  '}',
  'const hits = rows.filter(ok)',
  'await fetch(source)',
  'return merge(a, b)',
  'if (!found) retry()',
  'emit(result)',
  'const next = plan.pop()',
  'check(next, rules)',
  'cache.set(key, value)',
  'while (open.length) step()',
  'let best = null',
  'best = pick(best, item)',
  'log("done", count)',
  'const ok = verify(proof)',
  'queue.push(task)',
]

export interface CodeScreen {
  texture: CanvasTexture
  /** Moves the code on. Call every frame while the agent works; it repaints at its own pace. */
  tick(seconds: number): void
  /** Paints one still frame (used when motion is reduced). */
  still(): void
  dispose(): void
}

export function createCodeScreen(colour: string, seed: number): CodeScreen {
  const canvas = document.createElement('canvas')
  canvas.width = WIDTH
  canvas.height = HEIGHT
  const context = canvas.getContext('2d')!
  const texture = new CanvasTexture(canvas)
  texture.colorSpace = SRGBColorSpace

  // A tiny repeatable random, so each robot scrolls a different sequence.
  let state = Math.floor(seed * 1000) + 7
  const random = () => {
    state = (state * 1664525 + 1013904223) % 4294967296
    return state / 4294967296
  }
  const makeLine = () => {
    const text = SNIPPETS[Math.floor(random() * SNIPPETS.length)]
    const indent = text === '}' ? 0 : Math.floor(random() * 3) * 2
    return { text: ' '.repeat(indent) + text, bright: 0.55 + random() * 0.45 }
  }

  let lines = Array.from({ length: VISIBLE }, makeLine)
  let sinceStep = 0
  let last = -1

  const paint = (offset: number) => {
    context.fillStyle = '#04070b'
    context.fillRect(0, 0, WIDTH, HEIGHT)
    context.font = '16px ui-monospace, Menlo, Consolas, monospace'
    context.textBaseline = 'top'
    lines.forEach((line, index) => {
      const y = index * LINE - offset
      context.globalAlpha = line.bright
      context.fillStyle = colour
      context.fillText(line.text, 12, y)
    })
    // The newest line ends in a blinking cursor.
    context.globalAlpha = 1
    context.fillStyle = colour
    const lastY = (lines.length - 1) * LINE - offset
    if (Math.floor(last * 4) % 2 === 0) context.fillRect(12 + lines.at(-1)!.text.length * 9.6 + 3, lastY + 2, 8, 16)
    context.globalAlpha = 1
    texture.needsUpdate = true
  }

  paint(0)

  return {
    texture,
    tick(seconds) {
      const dt = last < 0 ? 0 : Math.min(0.1, seconds - last)
      last = seconds
      sinceStep += dt
      while (sinceStep >= STEP_SECONDS) {
        sinceStep -= STEP_SECONDS
        lines = [...lines.slice(1), makeLine()]
      }
      paint((sinceStep / STEP_SECONDS) * LINE) // slides smoothly between steps
    },
    still() {
      paint(0)
    },
    dispose() {
      texture.dispose()
    },
  }
}
