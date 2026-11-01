import { useRef } from 'react'
import { motion, useScroll, useTransform } from 'motion/react'
import type { MotionValue } from 'motion/react'
import { usePrefersReducedMotion } from '../../hooks/usePrefersReducedMotion'

interface ScrollWordsProps {
  text: string
  className?: string
}

/**
 * A sentence that "lights up" word by word as it scrolls up the window: each
 * word starts faint and becomes solid in turn, left to right.
 *
 * HOW
 *   `useScroll` turns the sentence's journey up the window into a number
 *   from 0 (just entering at the bottom) to 1 (well up the window). That
 *   range is cut into equal slices, one per word, and each word fades in
 *   during its own slice.
 *
 * With reduced motion on, the sentence is simply shown.
 */
export function ScrollWords({ text, className }: ScrollWordsProps) {
  const reduceMotion = usePrefersReducedMotion()
  const sentenceRef = useRef<HTMLParagraphElement>(null)

  // 0 when the sentence's top is 90% down the window, 1 when it is 35% down.
  const { scrollYProgress } = useScroll({ target: sentenceRef, offset: ['start 0.9', 'start 0.35'] })

  if (reduceMotion) {
    return <p className={className}>{text}</p>
  }

  const words = text.split(' ')

  return (
    <p ref={sentenceRef} className={className}>
      {words.map((word, index) => (
        <Word key={`${word}-${index}`} progress={scrollYProgress} from={index / words.length} to={(index + 1) / words.length}>
          {word}
        </Word>
      ))}
    </p>
  )
}

interface WordProps {
  children: string
  progress: MotionValue<number>
  /** The slice of the scroll in which this word fades in. */
  from: number
  to: number
}

function Word({ children, progress, from, to }: WordProps) {
  const opacity = useTransform(progress, [from, to], [0.16, 1])

  return (
    // `inline-block` lets each word be faded on its own; the margin is the space between words.
    <motion.span style={{ opacity }} className="mr-[0.26em] inline-block">
      {children}
    </motion.span>
  )
}
