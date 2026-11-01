import { useRef } from 'react'
import { motion, useScroll, useTransform } from 'motion/react'
import { buildPack } from '../../content/welcome'
import type { PackEntry } from '../../content/welcome'
import { usePrefersReducedMotion } from '../../hooks/usePrefersReducedMotion'
import { Reveal } from '../ui/Reveal'
import { Tag } from '../ui/Tag'

/** Left padding for each level of the file tree (the class number is pixels). */
const indentByDepth: Record<PackEntry['depth'], string> = {
  0: 'pl-0',
  1: 'pl-20',
  2: 'pl-40',
}

/**
 * Explains the build pack on the left and shows its folder layout on the
 * right, in a dark card that looks like a file browser.
 *
 * Two scroll effects:
 *   - the card drifts upward a little faster than the page ("parallax"),
 *     which makes it seem to float above the background
 *   - its rows appear one after another, top to bottom, the first time the
 *     card comes into view
 *
 * The layout is labeled as an example: it is the planned structure, not the
 * output of a real run.
 */
export function BuildPack() {
  const reduceMotion = usePrefersReducedMotion()
  const sectionRef = useRef<HTMLElement>(null)

  // 0 as the section enters at the bottom of the window, 1 as it leaves at the top.
  const { scrollYProgress } = useScroll({ target: sectionRef, offset: ['start end', 'end start'] })
  const drift = useTransform(scrollYProgress, [0, 1], [70, -70])

  return (
    <section id="build-pack" ref={sectionRef} className="bg-sage/55 px-20 py-72 md:px-32 md:py-112">
      <div className="mx-auto grid max-w-page items-center gap-40 lg:grid-cols-2 lg:gap-72">
        <Reveal>
          <Tag tone="morning">{buildPack.tag}</Tag>
          <h2 className="mt-20 text-heading-fluid text-ink">{buildPack.heading}</h2>
          <p className="mt-20 max-w-480 text-body-lg text-stone">{buildPack.summary}</p>

          <ul className="mt-32 max-w-480">
            {buildPack.points.map((point) => (
              <li key={point} className="border-t border-ink/12 py-16 text-body text-ink last:border-b">
                {point}
              </li>
            ))}
          </ul>
        </Reveal>

        <motion.div style={{ y: reduceMotion ? 0 : drift }}>
          <div className="rounded-[24px] bg-forest p-24 shadow-lift md:p-32">
            <div className="flex items-center justify-between gap-16">
              {/* Three dots, as on the title bar of a window. */}
              <span aria-hidden="true" className="flex gap-6">
                <span className="size-10 rounded-full bg-white/25" />
                <span className="size-10 rounded-full bg-white/25" />
                <span className="size-10 rounded-full bg-white/25" />
              </span>
              <Tag tone="forest">{buildPack.exampleLabel}</Tag>
            </div>

            <ul className="mt-24 font-mono text-body-sm">
              {buildPack.entries.map((entry, index) => (
                <motion.li
                  key={`${entry.depth}-${entry.name}`}
                  className={`flex items-baseline justify-between gap-16 py-6 ${indentByDepth[entry.depth]}`}
                  // Each row slides in from the left, a beat after the one above it.
                  initial={reduceMotion ? false : { opacity: 0, x: -14 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true, margin: '0px 0px -12% 0px' }}
                  transition={{ duration: 0.45, delay: index * 0.045, ease: [0.22, 1, 0.36, 1] }}
                >
                  <span className={entry.kind === 'folder' ? 'text-white' : 'text-sage'}>{entry.name}</span>
                  {entry.note && <span className="hidden text-right text-caption text-white/55 sm:inline">{entry.note}</span>}
                </motion.li>
              ))}
            </ul>
          </div>
        </motion.div>
      </div>
    </section>
  )
}
