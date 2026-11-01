import { useRef } from 'react'
import { motion, useScroll, useTransform } from 'motion/react'
import type { MotionValue } from 'motion/react'
import { journey } from '../../content/welcome'
import type { JourneyStep } from '../../content/welcome'
import { usePrefersReducedMotion } from '../../hooks/usePrefersReducedMotion'
import { Reveal } from '../ui/Reveal'
import { Tag } from '../ui/Tag'

/*
 * The path is drawn in its own small coordinate system: 120 units wide, and
 * 100 units tall for every step. It swings left for the first step, right
 * for the second, and so on, like the river in the hero's picture.
 */
const PATH_WIDTH = 120
const STEP_HEIGHT = 100
const LEFT_BEND = 18
const RIGHT_BEND = 102

/** Which side the path bends to at a step: left for the 1st, 3rd, 5th ... */
function bendOf(index: number): number {
  return index % 2 === 0 ? LEFT_BEND : RIGHT_BEND
}

/**
 * Builds the path's shape as SVG drawing commands.
 * For each step: curve from the middle out to the bend, then back to the middle.
 */
function buildPath(stepCount: number): string {
  let commands = `M${PATH_WIDTH / 2} 0`
  for (let index = 0; index < stepCount; index++) {
    const bend = bendOf(index)
    const top = index * STEP_HEIGHT
    const middle = top + STEP_HEIGHT / 2
    const bottom = top + STEP_HEIGHT
    commands += ` C${PATH_WIDTH / 2} ${top + 22} ${bend} ${middle - 22} ${bend} ${middle}`
    commands += ` S${PATH_WIDTH / 2} ${bottom - 22} ${PATH_WIDTH / 2} ${bottom}`
  }
  return commands
}

/**
 * "How it works": the seven steps laid out along a winding path.
 *
 * As the page scrolls, the path draws itself from top to bottom, and each
 * step's marker lights up as the line reaches it. The steps sit on
 * alternating sides of the path on wide screens, and all to its right on
 * phones.
 *
 * The drawing uses a neat trick: `pathLength` on a motion path is "how much
 * of the line is drawn", from 0 (none) to 1 (all), so it can be tied directly
 * to how far the page has scrolled through this section.
 */
export function Journey() {
  const reduceMotion = usePrefersReducedMotion()
  const stepsRef = useRef<HTMLDivElement>(null)
  const stepCount = journey.steps.length

  // 0 when the top of the steps is 70% down the window, 1 when their bottom is 55% down.
  const { scrollYProgress } = useScroll({ target: stepsRef, offset: ['start 0.7', 'end 0.55'] })
  const path = buildPath(stepCount)

  return (
    <section id="how-it-works" className="px-20 py-72 md:px-32 md:py-112">
      <div className="mx-auto max-w-page">
        <Reveal className="mx-auto max-w-760 text-center">
          <Tag tone="morning">{journey.tag}</Tag>
          <h2 className="mt-20 text-heading-fluid text-ink">{journey.heading}</h2>
          <p className="mt-16 text-body-lg text-stone">{journey.summary}</p>
        </Reveal>

        <div ref={stepsRef} className="relative mt-56 md:mt-72">
          {/* The path: a narrow column on the left on phones, in the middle on wide screens. */}
          <div aria-hidden="true" className="pointer-events-none absolute inset-y-0 left-0 w-56 md:left-1/2 md:w-120 md:-translate-x-1/2">
            {/* `preserveAspectRatio="none"` stretches the drawing to the column's real height. */}
            <svg viewBox={`0 0 ${PATH_WIDTH} ${stepCount * STEP_HEIGHT}`} preserveAspectRatio="none" className="size-full overflow-visible" fill="none">
              {/* The faint full path, and the solid part drawn so far. `non-scaling-stroke` keeps the line the same thickness however the drawing is stretched. */}
              <path d={path} className="stroke-ink/12" strokeWidth="2" vectorEffect="non-scaling-stroke" />
              <motion.path
                d={path}
                className="stroke-moss"
                strokeWidth="3"
                strokeLinecap="round"
                vectorEffect="non-scaling-stroke"
                style={{ pathLength: reduceMotion ? 1 : scrollYProgress }}
              />
            </svg>

            {journey.steps.map((step, index) => (
              <StepMarker
                key={step.title}
                // Where along the path this marker sits, as a share of the path's length.
                reachedAt={(index + 0.5) / stepCount}
                leftPercent={(bendOf(index) / PATH_WIDTH) * 100}
                topPercent={((index + 0.5) / stepCount) * 100}
                progress={scrollYProgress}
                reduceMotion={reduceMotion}
              />
            ))}
          </div>

          <ol>
            {journey.steps.map((step, index) => (
              <StepRow key={step.title} step={step} number={index + 1} onLeft={index % 2 === 0} />
            ))}
          </ol>
        </div>
      </div>
    </section>
  )
}

interface StepMarkerProps {
  reachedAt: number
  leftPercent: number
  topPercent: number
  progress: MotionValue<number>
  reduceMotion: boolean
}

/** Colors of a marker before and after the line reaches it. They match `dawn` and `moss` in tokens.css. */
const MARKER_WAITING = '#f8f3ed'
const MARKER_REACHED = '#4c6b53'

/** The round marker on the path for one step. It fills in and grows a little when the line reaches it. */
function StepMarker({ reachedAt, leftPercent, topPercent, progress, reduceMotion }: StepMarkerProps) {
  // Each of these watches how much of the path is drawn and flips when it passes this marker.
  const backgroundColor = useTransform(progress, (drawn): string => (drawn >= reachedAt ? MARKER_REACHED : MARKER_WAITING))
  const scale = useTransform(progress, (drawn): number => (drawn >= reachedAt ? 1 : 0.7))

  const classes = 'absolute size-16 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-moss'
  const place = { left: `${leftPercent}%`, top: `${topPercent}%` }

  if (reduceMotion) {
    return <span className={classes} style={{ ...place, backgroundColor: MARKER_REACHED }} />
  }

  return (
    // The CSS transition turns the sudden flip into a quick, smooth change.
    <motion.span className={`${classes} transition-[background-color,scale] duration-300`} style={{ ...place, backgroundColor, scale }} />
  )
}

interface StepRowProps {
  step: JourneyStep
  number: number
  /** On wide screens: true puts the text left of the path, false puts it right. */
  onLeft: boolean
}

/**
 * One step's text. Every row is the same height, which is what lets the
 * markers above be placed at even distances along the path.
 */
function StepRow({ step, number, onLeft }: StepRowProps) {
  const side = onLeft ? 'md:mr-auto md:pr-96 md:text-right' : 'md:ml-auto md:pl-96'

  return (
    <li className="flex h-200 items-center pl-72 md:h-180 md:pl-0">
      <div className={`w-full md:w-1/2 ${side}`}>
        <Reveal>
          {/* "01", "02", ... large and faint, like a milestone on a trail. */}
          <span className="font-display text-heading-lg font-heavy text-moss/35">{String(number).padStart(2, '0')}</span>
          <h3 className="mt-4 text-heading-sm text-ink">{step.title}</h3>
          <p className={`mt-8 max-w-440 text-body text-stone ${onLeft ? 'md:ml-auto' : ''}`}>{step.text}</p>
        </Reveal>
      </div>
    </li>
  )
}
