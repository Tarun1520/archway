/**
 * Draws what is shown on the laptop's screen, and on its keyboard.
 *
 * These are drawn with the browser's 2D canvas (the same tool used for
 * charts and simple games) and then used as textures in the 3D scene.
 *
 * The screen shows a PREVIEW of the planned Archway studio, laid out as the
 * implementation guide describes it. It is labeled "Preview" on the screen
 * itself: the studio is not built yet, and nothing on it is real data.
 */

const COLORS = {
  onyx: '#171721',
  graphite: '#1e1e2a',
  obsidian: '#272735',
  slate: '#70707d',
  ash: '#c3c3cc',
  ivory: '#ededf3',
  cobalt: '#5266eb',
}

const FONT = "'Inter Variable', system-ui, sans-serif"

/** The steps of the Archway workflow, in order, as shown in the graph on screen. */
const WORKFLOW_STEPS = ['Describe', 'Confirm', 'Research', 'Evaluate', 'Propose', 'Select', 'Build pack']

/** How many of those steps are drawn as finished in the preview. */
const FINISHED_STEPS = 3

/** Draws a rectangle with rounded corners and fills it. */
function fillRounded(context: CanvasRenderingContext2D, x: number, y: number, width: number, height: number, radius: number, color: string) {
  context.fillStyle = color
  context.beginPath()
  context.roundRect(x, y, width, height, radius)
  context.fill()
}

function drawText(context: CanvasRenderingContext2D, text: string, x: number, y: number, size: number, color: string, weight = 400) {
  context.font = `${weight} ${size}px ${FONT}`
  context.fillStyle = color
  context.fillText(text, x, y)
}

/**
 * Draws the studio preview onto `canvas`.
 * The canvas should be 1280 x 800 (a 16:10 laptop screen).
 */
export function drawStudioPreview(canvas: HTMLCanvasElement): void {
  const context = canvas.getContext('2d')
  if (!context) {
    return
  }
  const { width, height } = canvas

  context.fillStyle = COLORS.onyx
  context.fillRect(0, 0, width, height)
  context.textBaseline = 'middle'

  // --- Top bar: brand, project, and the Preview label ----------------------
  drawText(context, 'ARCHWAY', 40, 44, 20, COLORS.ivory, 480)
  drawText(context, 'Family recipe manager', 190, 44, 20, COLORS.ash)
  fillRounded(context, width - 168, 24, 128, 40, 20, COLORS.obsidian)
  drawText(context, 'Preview', width - 138, 45, 19, COLORS.ivory, 480)
  context.fillStyle = COLORS.obsidian
  context.fillRect(0, 86, width, 2)

  // --- Left column: the journey so far -------------------------------------
  drawText(context, 'Workflow', 40, 132, 18, COLORS.slate, 480)
  WORKFLOW_STEPS.forEach((step, index) => {
    const y = 184 + index * 56
    const finished = index < FINISHED_STEPS
    const current = index === FINISHED_STEPS

    if (current) {
      fillRounded(context, 28, y - 22, 236, 44, 22, COLORS.graphite)
    }
    // A filled dot for finished steps, a ring for the rest.
    context.beginPath()
    context.arc(54, y, 7, 0, Math.PI * 2)
    if (finished || current) {
      context.fillStyle = current ? COLORS.cobalt : COLORS.ivory
      context.fill()
    } else {
      context.strokeStyle = COLORS.slate
      context.lineWidth = 2
      context.stroke()
    }
    drawText(context, step, 78, y + 1, 20, finished || current ? COLORS.ivory : COLORS.slate)
  })

  // --- Middle: the headline card and three option cards --------------------
  const mainX = 300
  const mainWidth = 620
  drawText(context, 'Evaluating candidates', mainX, 136, 34, COLORS.ivory, 480)
  drawText(context, 'Checking licenses and hard constraints before judging fit.', mainX, 180, 18, COLORS.ash)

  fillRounded(context, mainX, 216, mainWidth, 250, 14, COLORS.graphite)
  drawText(context, 'Evidence coverage', mainX + 28, 256, 18, COLORS.ash)
  // A simple line chart: a made-up shape, there to suggest a chart.
  const chartPoints = [0.25, 0.32, 0.3, 0.46, 0.42, 0.58, 0.55, 0.7, 0.66, 0.8, 0.78, 0.9]
  context.beginPath()
  chartPoints.forEach((value, index) => {
    const x = mainX + 28 + (index / (chartPoints.length - 1)) * (mainWidth - 56)
    const y = 440 - value * 150
    if (index === 0) {
      context.moveTo(x, y)
    } else {
      context.lineTo(x, y)
    }
  })
  context.strokeStyle = COLORS.ivory
  context.lineWidth = 3
  context.stroke()

  const cardWidth = (mainWidth - 32) / 3
  ;['Simplest', 'Extensible', 'Most reuse'].forEach((label, index) => {
    const x = mainX + index * (cardWidth + 16)
    fillRounded(context, x, 490, cardWidth, 250, 14, COLORS.graphite)
    drawText(context, `Option ${'ABC'[index]}`, x + 22, 528, 17, COLORS.slate, 480)
    drawText(context, label, x + 22, 562, 22, COLORS.ivory, 480)
    // Grey bars stand in for lines of text.
    for (let line = 0; line < 4; line++) {
      fillRounded(context, x + 22, 606 + line * 28, cardWidth - 44 - (line % 2) * 40, 10, 5, COLORS.obsidian)
    }
  })

  // --- Right column: evidence ----------------------------------------------
  const sideX = 952
  const sideWidth = width - sideX - 40
  drawText(context, 'Evidence', sideX, 132, 18, COLORS.slate, 480)
  for (let item = 0; item < 5; item++) {
    const y = 164 + item * 116
    fillRounded(context, sideX, y, sideWidth, 100, 14, COLORS.graphite)
    fillRounded(context, sideX + 20, y + 22, 130, 12, 6, COLORS.ash)
    fillRounded(context, sideX + 20, y + 48, sideWidth - 40, 9, 4, COLORS.obsidian)
    fillRounded(context, sideX + 20, y + 68, sideWidth - 90, 9, 4, COLORS.obsidian)
  }
}

/**
 * Draws a laptop keyboard and trackpad, seen from above, onto `canvas`.
 * The canvas should be about 1040 x 720 (the shape of the laptop's top face).
 */
export function drawKeyboard(canvas: HTMLCanvasElement): void {
  const context = canvas.getContext('2d')
  if (!context) {
    return
  }
  const { width, height } = canvas

  // The aluminium top face.
  context.fillStyle = '#c4c7cd'
  context.fillRect(0, 0, width, height)

  // The dark well the keys sit in.
  const wellX = 70
  const wellY = 60
  const wellWidth = width - 140
  const wellHeight = 330
  fillRounded(context, wellX, wellY, wellWidth, wellHeight, 12, '#0e0e11')

  // Six rows of keys. The bottom row has a wide space bar in the middle.
  const rows = 6
  const columns = 14
  const gap = 6
  const keyWidth = (wellWidth - gap * (columns + 1)) / columns
  const keyHeight = (wellHeight - gap * (rows + 1)) / rows

  for (let row = 0; row < rows; row++) {
    const y = wellY + gap + row * (keyHeight + gap)
    for (let column = 0; column < columns; column++) {
      const x = wellX + gap + column * (keyWidth + gap)
      const isSpaceBarStart = row === rows - 1 && column === 4
      const insideSpaceBar = row === rows - 1 && column > 4 && column < 9

      if (insideSpaceBar) {
        continue // already covered by the wide key
      }
      const keySpan = isSpaceBarStart ? 5 : 1
      fillRounded(context, x, y, keyWidth * keySpan + gap * (keySpan - 1), keyHeight, 6, '#26262c')
    }
  }

  // The trackpad: a slightly lighter rectangle with a fine outline.
  const padWidth = 400
  const padHeight = 240
  const padX = (width - padWidth) / 2
  const padY = wellY + wellHeight + 44
  fillRounded(context, padX, padY, padWidth, padHeight, 14, '#cfd2d8')
  context.strokeStyle = 'rgba(0, 0, 0, 0.16)'
  context.lineWidth = 2
  context.beginPath()
  context.roundRect(padX, padY, padWidth, padHeight, 14)
  context.stroke()
}
