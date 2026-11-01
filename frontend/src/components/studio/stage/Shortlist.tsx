import { studioUi } from '../../../content/studio'
import type { ResearchSnapshot } from '../../../lib/api/types'
import { decidedByModel, receiptsById, summarise, totals, verdictsById } from '../../../lib/decisions'
import { capabilityTitle, licenseView, safeHref, shortCount } from '../../../lib/research'
import { coreFirst, picksFor } from '../../../lib/shortlist'
import { sourceRows } from '../../../lib/sources'
import { DecisionBadge, RulesBadge } from '../DecisionBadge'
import { SourceBadge } from '../SourceBadge'
import { ArrowRight, StudioButton } from '../StudioButton'

/**
 * The result, minimal: each capability (core first) as a row, its name on the
 * left in large type and its best few parts on the right. One line per part:
 * what it gives, then its license, adoption and eligibility in mono. The full
 * picture (every find, the judge's notes, evidence) is in Details.
 */
export function Shortlist({
  research, onDetails, onStartOptions, working = false, canStartOptions = false,
}: {
  research: ResearchSnapshot
  onDetails: () => void
  /** Asks for architecture options (the next step). Only offered when the run has finished its decisions. */
  onStartOptions?: () => void
  working?: boolean
  canStartOptions?: boolean
}) {
  const verdicts = verdictsById(research.eligibility ?? [])
  const receipts = receiptsById(research.receipts ?? [])
  const count = totals(research.eligibility ?? [], research.receipts ?? [])
  // Where this run really looked (recorded by the backend as its tools ran), grouped; unused sources are not shown.
  const sources = sourceRows(research)
  return (
    <section className="flex flex-col">
      {/* Who decided what, once, at the top: the badges on each part below mean exactly this. */}
      <div className="mb-32 flex max-w-3xl flex-col gap-10 rounded-card border border-line bg-carbon/70 p-16">
        <p className="flex flex-wrap items-center gap-10 text-[15px] leading-[1.6] text-chalk/90">
          <RulesBadge /> Plain code decides what may be reused: license, archived, finished apps. It always has the last word.
        </p>
        <p className="flex flex-wrap items-center gap-10 text-[15px] leading-[1.6] text-chalk/90">
          <DecisionBadge engine={count.engine} />
          {count.engine.id === 'laya'
            ? `Laya, the open-source decision model on this computer, answered ${count.answered} question${count.answered === 1 ? '' : 's'} about fit and integration risk`
            : count.answered > 0
              ? `${count.engine.label} answered ${count.answered} question${count.answered === 1 ? '' : 's'} about fit and integration risk`
              : 'The decision model was not asked, so nothing here was decided by one'}
          {count.notAsked > 0 && `; ${count.notAsked} could not be asked and were left as "not asked", never guessed`}
          {count.byModel > 0 && `. Its answer ruled out ${count.byModel} part${count.byModel === 1 ? '' : 's'}`}.
        </p>
      </div>
      {/* Where the agents looked, once, at the top: the same kind of badge as above, only for sources this run used. */}
      {sources.length > 0 && (
        <div className="mb-32 flex max-w-3xl flex-col gap-10 rounded-card border border-line bg-carbon/70 p-16">
          {sources.map((row) => (
            <p key={row.badges.map((b) => b.name).join()} className="flex flex-wrap items-center gap-10 text-[15px] leading-[1.6] text-chalk/90">
              {row.badges.map((badge) => (
                <SourceBadge key={badge.name} name={badge.name} detail={badge.detail} />
              ))}
              {row.text}
            </p>
          ))}
        </div>
      )}
      <ol className="border-t border-line">
        {coreFirst(research.capabilities).map((capability) => {
          const picks = picksFor(capability.id, research.components, verdicts)
          return (
            <li key={capability.id} className="grid gap-24 border-b border-line py-40 lg:grid-cols-[5fr_7fr]">
              <div>
                <p className="font-code text-label uppercase text-smoke">
                  <span className={capability.priority === 'supporting' ? '' : 'text-vermilion'}>
                    {capability.priority === 'supporting' ? studioUi.supporting : studioUi.core}
                  </span>{' '}
                  · {capability.id}
                </p>
                <h2 className="mt-12 text-h3 font-bold">{capabilityTitle(capability.name)}</h2>
                <p className="mt-12 max-w-md text-[15px] leading-[1.6] text-smoke">{capability.need}</p>
              </div>

              {picks.length === 0 ? (
                <p className="self-center text-[16px] text-smoke">{studioUi.noPick}</p>
              ) : (
                <ul className="flex flex-col">
                  {picks.map(({ component, verdict }) => {
                    const href = safeHref(component.facts.url)
                    const license = licenseView(component.facts)
                    const adoption = component.facts.downloads_last_month
                      ? `${shortCount(component.facts.downloads_last_month)}/mo`
                      : component.facts.stars !== null
                        ? `★ ${shortCount(component.facts.stars)}`
                        : null
                    const decision = summarise(receipts.get(component.id) ?? [])
                    return (
                      <li key={component.id} className="border-b border-line py-16 first:pt-0 last:border-b-0">
                        <p className="flex flex-wrap items-baseline justify-between gap-12">
                          {href ? (
                            <a
                              href={href}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-[20px] font-semibold text-chalk underline decoration-line decoration-2 underline-offset-[6px] transition-colors duration-150 hover:decoration-vermilion"
                            >
                              {component.name}
                            </a>
                          ) : (
                            <span className="text-[20px] font-semibold text-chalk">{component.name}</span>
                          )}
                          <span className="font-code text-label uppercase text-smoke">{[license.label, adoption].filter(Boolean).join(' · ')}</span>
                        </p>
                        <p className="mt-6 line-clamp-2 text-[15px] leading-[1.6] text-smoke">{component.provides}</p>
                        {/* Who said what about this part: the gate (rules) and the decision model (Laya). */}
                        <p className="mt-10 flex flex-wrap items-center gap-x-10 gap-y-6 text-[13px] text-smoke">
                          {decidedByModel(verdict) ? <DecisionBadge engine={decision?.source ?? count.engine} /> : <RulesBadge />}
                          <span className={verdict?.status === 'review_required' ? 'text-vermilion' : 'text-chalk/85'}>
                            {studioUi.eligibility[verdict?.status ?? 'eligible']}
                          </span>
                          <span aria-hidden="true">·</span>
                          {decision ? (
                            <>
                              <DecisionBadge engine={decision.source} />
                              <span className="text-chalk/85">
                                {decision.evaluated
                                  ? [decision.fit.join(', '), decision.risk && `${decision.risk} risk`, decision.needsReview && 'check it yourself']
                                      .filter(Boolean)
                                      .join(' · ')
                                  : 'could not be asked'}
                              </span>
                            </>
                          ) : (
                            <span>not asked</span>
                          )}
                        </p>
                      </li>
                    )
                  })}
                </ul>
              )}
            </li>
          )
        })}
      </ol>
      <div className="flex flex-wrap items-center gap-24 pt-32">
        {onStartOptions && (
          <div className="flex flex-col gap-8">
            <StudioButton onClick={onStartOptions} disabled={!canStartOptions || working}>
              {studioUi.draftOptions} <ArrowRight />
            </StudioButton>
            <p className="max-w-md text-[14px] text-smoke">{working ? studioUi.draftingNow : studioUi.draftOptionsHint}</p>
          </div>
        )}
        <StudioButton variant="ghost" className="px-0" onClick={onDetails}>
          {studioUi.seeDetails} <ArrowRight />
        </StudioButton>
      </div>
    </section>
  )
}
