import type { ComponentCandidate, DecisionReceipt, EligibilityVerdict } from '../../lib/api/types'
import { ELIGIBILITY_LABEL, decidedByModel, receiptsById, summarise, totals } from '../../lib/decisions'
import { DecisionBadge, RulesBadge } from './DecisionBadge'

/**
 * The Decisions tab: how many components landed in each eligibility status, who made the calls (the plain
 * rules, or the decision model, Laya, answering questions), and then every component with both answers side by side.
 */
export function DecisionsSummary({
  eligibility, receipts, components = [],
}: { eligibility: EligibilityVerdict[]; receipts: DecisionReceipt[]; components?: ComponentCandidate[] }) {
  const counts = (['eligible', 'review_required', 'unresolved', 'excluded'] as const).map((status) => ({
    status,
    count: eligibility.filter((v) => v.status === status).length,
  }))
  const count = totals(eligibility, receipts)
  const byComponent = receiptsById(receipts)
  const named = new Map(components.map((c) => [c.id, c]))
  // Ones the model answered about come first, then the rest, each in the order they were found.
  const rows = eligibility.map((verdict) => ({ verdict, summary: summarise(byComponent.get(verdict.component_id) ?? []) }))
  return (
    <div className="flex flex-col gap-32">
      <dl className="grid grid-cols-2 border-t border-line md:grid-cols-4">
        {counts.map(({ status, count }) => (
          <div key={status} className="border-b border-line py-20 pr-16">
            <dt className="font-code text-label uppercase text-smoke">{ELIGIBILITY_LABEL[status]}</dt>
            <dd className="mt-6 font-code text-h2 font-semibold text-chalk">{count}</dd>
          </div>
        ))}
      </dl>

      <div className="flex max-w-3xl flex-col gap-10 rounded-card border border-line bg-carbon/70 p-16">
        <p className="flex flex-wrap items-center gap-10 text-[15px] leading-[1.6] text-chalk/90">
          <RulesBadge />
          Plain rules decided {count.byRules} of {count.components} components. They look at the license, whether the repository is archived, and whether it is a finished app.
        </p>
        <p className="flex flex-wrap items-center gap-10 text-[15px] leading-[1.6] text-chalk/90">
          <DecisionBadge engine={count.engine} />
          {receipts.length === 0
            ? 'No decision receipts yet.'
            : `${count.engine.label === 'LAYA' ? 'Laya' : count.engine.label} answered ${count.answered} question${count.answered === 1 ? '' : 's'}${
                count.notAsked > 0 ? `; ${count.notAsked} could not be asked and are marked not asked` : ''
              }. ${count.byModel > 0 ? `Its answer ruled out ${count.byModel} component${count.byModel === 1 ? '' : 's'}.` : 'None of its answers ruled a component out; the rules decided every status.'}`}
        </p>
        <p className="text-[14px] text-smoke">
          The decision model informs; the rules decide. A model's answer can never lift an excluded component back in.
          {count.engine.id === 'laya' && " Laya's percentages are its own raw scores, not calibrated chances: a 'yes' near 50% is a weak yes."}
        </p>
      </div>

      <ul className="flex flex-col border-t border-line">
        {rows.map(({ verdict, summary }) => {
          const component = named.get(verdict.component_id)
          return (
            <li key={verdict.component_id} className="grid gap-12 border-b border-line py-20 lg:grid-cols-[4fr_3fr_5fr]">
              <div className="min-w-0">
                <p className="break-all text-[17px] font-semibold text-chalk">{component?.name ?? verdict.component_id}</p>
                {component && <p className="mt-4 line-clamp-2 text-[14px] text-smoke">{component.provides}</p>}
              </div>
              <div className="flex flex-col gap-6">
                <p className="flex flex-wrap items-center gap-8">
                  {decidedByModel(verdict) && summary ? <DecisionBadge engine={summary.source} /> : <RulesBadge />}
                  <span className="text-[15px] text-chalk">{ELIGIBILITY_LABEL[verdict.status]}</span>
                </p>
                {verdict.reasons.length > 0 && <p className="text-[13px] leading-[1.5] text-smoke">{verdict.reasons.join('; ')}</p>}
              </div>
              <div className="flex flex-col gap-6">
                {summary ? (
                  <>
                    <p className="flex items-center gap-8">
                      <DecisionBadge engine={summary.source} />
                      <span className="font-code text-[11px] uppercase text-smoke">{summary.mode}</span>
                    </p>
                    {summary.evaluated ? (
                      <ul className="flex flex-col gap-2 text-[13px]">
                        {summary.lines.map((line, index) => (
                          <li key={index} className="flex flex-wrap gap-x-8">
                            <span className="text-smoke">{line.question}</span>
                            <span className="text-chalk">{line.answer ?? 'not asked'}</span>
                            {line.confidence !== null && <span className="font-code text-smoke">{Math.round(line.confidence * 100)}%</span>}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-[13px] text-smoke">not asked: nothing was guessed</p>
                    )}
                  </>
                ) : (
                  <p className="flex items-center gap-8 text-[13px] text-smoke">
                    <DecisionBadge engine={count.engine.id === 'laya' ? { id: 'none', label: 'NOT ASKED', detail: 'The decision model was not asked about this one.' } : count.engine} />
                    not asked
                  </p>
                )}
              </div>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
