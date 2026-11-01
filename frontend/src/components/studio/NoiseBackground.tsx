import {
  motion,
  useAnimationFrame,
  useMotionTemplate,
  useMotionValue,
  useSpring,
  useTransform,
  type MotionValue,
} from 'motion/react'
import { useEffect, useRef } from 'react'
import type { CSSProperties, ReactNode } from 'react'

/**
 * A frame of slowly drifting colour with a fine film grain, for buttons.
 *
 * Ported from Aceternity UI's "Noise Background"
 * (https://ui.aceternity.com/components/noise-background). Same idea and
 * motion: three soft colour blobs wander inside the frame, following a spring
 * so they glide, over a still grain. Changes so it fits this app:
 *   - No shadcn/ui or `cn` helper; colours come from the studio palette.
 *   - The grain is a small built-in picture (an SVG noise filter), not a file
 *     loaded from Aceternity's website.
 *   - Sizes use this project's 1px spacing unit.
 *   - `animating` stops the drift (used for disabled buttons and for people
 *     who asked for reduced motion).
 */

const GRAIN =
  "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.8' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E\")"

/** One soft colour blob. It sits at the wandering point, scaled by `multiplier`, so the three drift apart. */
function GradientLayer({
  springX,
  springY,
  colour,
  opacity,
  multiplier,
}: {
  springX: MotionValue<number>
  springY: MotionValue<number>
  colour: string
  opacity: number
  multiplier: number
}) {
  const x = useTransform(springX, (value) => value * multiplier)
  const y = useTransform(springY, (value) => value * multiplier)
  const background = useMotionTemplate`radial-gradient(circle at ${x}px ${y}px, ${colour} 0%, transparent 50%)`
  return <motion.div aria-hidden="true" className="absolute inset-0" style={{ opacity, background }} />
}

interface NoiseBackgroundProps {
  children?: ReactNode
  /** Classes for the frame (its shape and size). */
  containerClassName?: string
  /** Classes for the content layer. */
  className?: string
  gradientColors?: string[]
  /** How visible the grain is, 0 to 1. */
  noiseIntensity?: number
  /** How fast the blobs wander. */
  speed?: number
  animating?: boolean
}

export function NoiseBackground({
  children,
  containerClassName = '',
  className = '',
  gradientColors = ['rgb(255, 61, 0)', 'rgb(255, 150, 70)', 'rgb(255, 205, 120)'],
  noiseIntensity = 0.2,
  speed = 0.1,
  animating = true,
}: NoiseBackgroundProps) {
  const frame = useRef<HTMLDivElement>(null)
  const x = useMotionValue(0)
  const y = useMotionValue(0)
  const springX = useSpring(x, { stiffness: 100, damping: 30 })
  const springY = useSpring(y, { stiffness: 100, damping: 30 })
  const stripX = useTransform(springX, (value) => value * 0.1 - 50)

  const velocity = useRef({ x: 0, y: 0 })
  const lastTurn = useRef(0)

  const pickVelocity = () => {
    const angle = Math.random() * Math.PI * 2
    const magnitude = speed * (0.5 + Math.random() * 0.5)
    return { x: Math.cos(angle) * magnitude, y: Math.sin(angle) * magnitude }
  }

  // Start in the middle of the frame, heading somewhere.
  useEffect(() => {
    const box = frame.current?.getBoundingClientRect()
    if (box) {
      x.set(box.width / 2)
      y.set(box.height / 2)
    }
    velocity.current = pickVelocity()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [speed])

  useAnimationFrame((time) => {
    if (!animating || !frame.current) return
    const box = frame.current.getBoundingClientRect()

    // A new direction every 1.5 to 3 seconds, and whenever it reaches an edge.
    if (time - lastTurn.current > 1500 + Math.random() * 1500) {
      velocity.current = pickVelocity()
      lastTurn.current = time
    }
    const padding = 12
    let nextX = x.get() + velocity.current.x * 16
    let nextY = y.get() + velocity.current.y * 16
    if (nextX < padding || nextX > box.width - padding || nextY < padding || nextY > box.height - padding) {
      velocity.current = pickVelocity()
      lastTurn.current = time
      nextX = Math.max(padding, Math.min(box.width - padding, nextX))
      nextY = Math.max(padding, Math.min(box.height - padding, nextY))
    }
    x.set(nextX)
    y.set(nextY)
  })

  return (
    <div
      ref={frame}
      className={`relative overflow-hidden bg-soot shadow-[0px_1px_0px_0px_#0a0a0a_inset,0px_1px_0px_0px_#262626] ${containerClassName}`}
      style={{ '--noise-opacity': noiseIntensity } as CSSProperties}
    >
      <GradientLayer springX={springX} springY={springY} colour={gradientColors[0]} opacity={0.55} multiplier={1} />
      <GradientLayer springX={springX} springY={springY} colour={gradientColors[1] ?? gradientColors[0]} opacity={0.4} multiplier={0.7} />
      <GradientLayer springX={springX} springY={springY} colour={gradientColors[2] ?? gradientColors[0]} opacity={0.32} multiplier={1.2} />

      {/* A soft strip of the same colours along the top edge. */}
      <motion.div
        aria-hidden="true"
        className="absolute inset-x-0 top-0 h-[3px] opacity-80 blur-[2px]"
        style={{ background: `linear-gradient(to right, ${gradientColors.join(', ')})`, x: animating ? stripX : 0 }}
      />

      {/* The still grain. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 opacity-[var(--noise-opacity)]"
        style={{ backgroundImage: GRAIN, backgroundSize: '160px 160px', mixBlendMode: 'overlay' }}
      />

      <div className={`relative z-10 ${className}`}>{children}</div>
    </div>
  )
}
