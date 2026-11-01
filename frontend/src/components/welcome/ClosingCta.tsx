import { useRef } from 'react'
import { motion, useScroll, useTransform } from 'motion/react'
import { closing } from '../../content/welcome'
import { usePrefersReducedMotion } from '../../hooks/usePrefersReducedMotion'
import { START_HREF, focusIdeaInput } from '../../lib/focusIdeaInput'
import { ButtonLink } from '../ui/Button'
import { Reveal } from '../ui/Reveal'

/**
 * The last block before the footer: the hero's two lines again, as an
 * invitation, inside a large card painted like the morning sky.
 *
 * As it scrolls into view the card grows from slightly small to full size,
 * and the arch behind the words rises into place.
 */
export function ClosingCta() {
  const reduceMotion = usePrefersReducedMotion()
  const cardRef = useRef<HTMLDivElement>(null)

  // 0 as the card enters at the bottom of the window, 1 when its top is 30% down.
  const { scrollYProgress } = useScroll({ target: cardRef, offset: ['start end', 'start 0.3'] })
  const grow = useTransform(scrollYProgress, [0, 1], [0.9, 1])
  const archRise = useTransform(scrollYProgress, [0, 1], [60, 0])

  return (
    <section className="px-20 py-72 md:px-32 md:py-112">
      <motion.div
        ref={cardRef}
        style={{ scale: reduceMotion ? 1 : grow }}
        className="bg-morning-sky relative mx-auto flex max-w-page flex-col items-center overflow-hidden rounded-[32px] px-24 py-112 text-center shadow-lift md:py-128"
      >
        <motion.svg
          aria-hidden="true"
          viewBox="0 0 100 100"
          preserveAspectRatio="xMidYMax meet"
          style={{ y: reduceMotion ? 0 : archRise }}
          className="pointer-events-none absolute inset-x-0 bottom-0 mx-auto h-[96%] w-full text-forest"
        >
          <path d="M20 100V46a30 30 0 0 1 60 0v54" fill="none" stroke="currentColor" strokeOpacity="0.14" strokeWidth="0.3" />
          <path d="M28 100V48a22 22 0 0 1 44 0v52" fill="none" stroke="currentColor" strokeOpacity="0.08" strokeWidth="0.3" />
        </motion.svg>

        <Reveal className="relative">
          <h2 className="font-display text-[clamp(40px,7vw,96px)] leading-[1.02] font-strong tracking-[-0.03em] text-ink">{closing.heading}</h2>
          <p className="mt-16 text-lead-fluid text-stone">{closing.summary}</p>
          <ButtonLink href={START_HREF} onClick={focusIdeaInput} size="lg" className="mt-40">
            {closing.actionLabel}
          </ButtonLink>
        </Reveal>
      </motion.div>
    </section>
  )
}
