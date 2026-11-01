import { useRef } from 'react'
import { motion, useScroll, useTransform } from 'motion/react'
import { marqueeWords } from '../../content/welcome'
import { usePrefersReducedMotion } from '../../hooks/usePrefersReducedMotion'

/**
 * A band of very large words (the names of the steps) that slides sideways
 * as the page scrolls past it: scroll down and it moves left, scroll up and
 * it moves back.
 *
 * It is decoration (the steps are listed properly elsewhere), so it is hidden
 * from screen readers.
 */
export function WordBand() {
  const reduceMotion = usePrefersReducedMotion()
  const bandRef = useRef<HTMLDivElement>(null)

  // 0 as the band enters at the bottom of the window, 1 as it leaves at the top.
  const { scrollYProgress } = useScroll({ target: bandRef, offset: ['start end', 'end start'] })
  const slide = useTransform(scrollYProgress, [0, 1], ['4%', '-42%'])

  return (
    <div ref={bandRef} aria-hidden="true" className="overflow-hidden py-40 md:py-56">
      <motion.div style={{ x: reduceMotion ? 0 : slide }} className="flex w-max items-center gap-40 whitespace-nowrap">
        {marqueeWords.map((word, index) => (
          // Every second word is drawn as an outline only, for rhythm.
          <span
            key={word}
            className={`font-display text-[clamp(56px,10vw,144px)] leading-none font-heavy tracking-[-0.03em] ${index % 2 === 0 ? 'text-forest' : 'text-outline'}`}
          >
            {word}
          </span>
        ))}
      </motion.div>
    </div>
  )
}
