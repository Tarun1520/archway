import { useRef } from 'react'
import type { ReactNode } from 'react'
import { motion, useScroll, useTransform } from 'motion/react'
import type { MotionValue } from 'motion/react'
import { features } from '../../content/welcome'
import type { Feature, FeatureIcon } from '../../content/welcome'
import { usePrefersReducedMotion } from '../../hooks/usePrefersReducedMotion'
import { ResumeIcon, RulesIcon, SourceIcon, SteerIcon } from '../ui/icons'
import { Reveal } from '../ui/Reveal'
import { Tag } from '../ui/Tag'

/** Maps the icon name used in the content file to the icon itself. */
const icons: Record<FeatureIcon, ReactNode> = {
  source: <SourceIcon size={40} />,
  rules: <RulesIcon size={40} />,
  steer: <SteerIcon size={40} />,
  resume: <ResumeIcon size={40} />,
}

/** Maps the color name used in the content file to the card's background. */
const backgrounds: Record<Feature['color'], string> = {
  blush: 'bg-blush',
  sky: 'bg-sky',
  sage: 'bg-sage',
  white: 'bg-white',
}

/** How far down the window each card sticks, and how much lower each later card sits, in pixels. */
const STICK_AT = 96
const STEP_DOWN = 20

/**
 * "Why Archway": four large cards that stack like a deck as the page scrolls.
 *
 * Each card is `sticky`: it scrolls up normally until it reaches the top of
 * the window, then holds there while the next card slides up and covers it.
 * Each one sticks a little lower than the last, so the edges of the cards
 * underneath stay visible, and the covered cards shrink slightly to look as
 * if they are receding.
 */
export function Features() {
  const reduceMotion = usePrefersReducedMotion()
  const deckRef = useRef<HTMLUListElement>(null)

  // 0 when the deck's top reaches the top of the window, 1 when its bottom reaches the bottom.
  const { scrollYProgress } = useScroll({ target: deckRef, offset: ['start start', 'end end'] })
  const count = features.items.length

  return (
    <section id="why-archway" className="px-20 py-72 md:px-32 md:py-112">
      <div className="mx-auto max-w-page">
        <Reveal className="max-w-760">
          <Tag tone="morning">{features.tag}</Tag>
          <h2 className="mt-20 text-heading-fluid text-ink">{features.heading}</h2>
        </Reveal>

        <ul ref={deckRef} className="mt-40 md:mt-56">
          {features.items.map((feature, index) => (
            <FeatureCard
              key={feature.title}
              feature={feature}
              index={index}
              count={count}
              progress={scrollYProgress}
              reduceMotion={reduceMotion}
            />
          ))}
        </ul>
      </div>
    </section>
  )
}

interface FeatureCardProps {
  feature: Feature
  index: number
  count: number
  progress: MotionValue<number>
  reduceMotion: boolean
}

function FeatureCard({ feature, index, count, progress, reduceMotion }: FeatureCardProps) {
  // From the moment this card is covered until the end of the deck, it
  // shrinks a little. Cards nearer the bottom of the pile shrink the most.
  const shrinkTo = 1 - (count - 1 - index) * 0.035
  const scale = useTransform(progress, [index / count, 1], [1, shrinkTo])

  return (
    <li className="sticky pb-20" style={{ top: STICK_AT + index * STEP_DOWN }}>
      <motion.article
        style={{ scale: reduceMotion ? 1 : scale }}
        className={`flex min-h-320 origin-top flex-col justify-between gap-40 rounded-[28px] p-32 shadow-lift md:min-h-360 md:flex-row md:items-end md:p-56 ${backgrounds[feature.color]}`}
      >
        <div className="max-w-560">
          <span className="font-mono text-caption text-stone">
            {String(index + 1).padStart(2, '0')} / {String(count).padStart(2, '0')}
          </span>
          <h3 className="mt-16 font-display text-[clamp(26px,3.4vw,44px)] leading-[1.12] font-strong tracking-[-0.02em] text-ink">
            {feature.title}
          </h3>
          <p className="mt-16 text-body-lg text-stone">{feature.text}</p>
        </div>

        {/* The icon in a white disc, like a seal in the corner of the card. */}
        <span aria-hidden="true" className="flex size-88 shrink-0 items-center justify-center rounded-full bg-white/70 text-forest md:size-112">
          {icons[feature.icon]}
        </span>
      </motion.article>
    </li>
  )
}
