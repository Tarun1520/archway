import { figures } from '../../content/welcome'
import { CountUp } from '../ui/CountUp'
import { Reveal } from '../ui/Reveal'

/**
 * A deep green band with four numbers that count up as they scroll into view.
 * The numbers are the real defaults of an Archway run.
 */
export function Figures() {
  return (
    <section className="bg-forest px-20 py-72 text-dawn md:px-32 md:py-112">
      <div className="mx-auto max-w-page">
        <Reveal>
          <h2 className="max-w-640 text-heading-fluid text-white">{figures.heading}</h2>
        </Reveal>

        <dl className="mt-56 grid grid-cols-2 gap-x-24 gap-y-40 lg:grid-cols-4">
          {figures.items.map((figure, index) => (
            <Reveal key={figure.label} delay={index * 0.08}>
              {/* A thin line above each figure, like a ruled column in a report. */}
              <div className="border-t border-white/20 pt-20">
                {/* <dd> is the value and <dt> its name; shown number first, label second. */}
                <dd className="flex items-baseline gap-8">
                  {figure.prefix && <span className="text-body-sm text-sage">{figure.prefix}</span>}
                  <CountUp value={figure.value} className="font-display text-[clamp(52px,7vw,96px)] leading-none font-heavy tracking-[-0.03em] text-white" />
                </dd>
                <dt className="mt-12 max-w-200 text-body text-sage">{figure.label}</dt>
              </div>
            </Reveal>
          ))}
        </dl>
      </div>
    </section>
  )
}
