import { motion, useReducedMotion } from 'motion/react'

interface StageHeadlineProps {
  number: number
  headline: string
  lead: string
}

/**
 * The step's poster headline: a huge, tight headline over a decorative step
 * number set in the divider colour behind it, and a short lead paragraph.
 * Type is the hero here; nothing else competes with it.
 */
export function StageHeadline({ number, headline, lead }: StageHeadlineProps) {
  const reduceMotion = useReducedMotion()
  return (
    <motion.header
      key={headline}
      initial={reduceMotion ? false : { opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.25, 0, 0, 1] }}
      className="relative"
    >
      {/* The big number is decoration: hidden from screen readers and on small screens. */}
      <span
        aria-hidden="true"
        className="pointer-events-none absolute -top-48 -left-8 hidden select-none font-tight text-deco font-black text-line md:block"
      >
        {String(number).padStart(2, '0')}
      </span>
      <h1 className="relative max-w-[14ch] text-h1 font-black md:text-[72px] lg:text-poster">
        {/* The anchor for "waiting" ripples: the centre of the words themselves (hooks/useRippleWhile.ts). */}
        <span data-ripple-anchor="headline">{headline}</span>
      </h1>
      {lead && <p className="relative mt-24 max-w-xl text-lead text-smoke">{lead}</p>}
    </motion.header>
  )
}
