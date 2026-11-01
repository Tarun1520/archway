import { statement } from '../../content/welcome'
import { ScrollWords } from '../ui/ScrollWords'

/**
 * One large sentence on its own, between the start screen and the steps.
 * Its words light up one after another as the page scrolls (ScrollWords).
 */
export function Statement() {
  return (
    <section className="px-20 py-112 md:px-32 md:py-128">
      <ScrollWords
        text={statement.text}
        className="mx-auto max-w-960 text-center font-display text-[clamp(30px,5vw,64px)] leading-[1.12] font-strong tracking-[-0.02em] text-ink"
      />
    </section>
  )
}
