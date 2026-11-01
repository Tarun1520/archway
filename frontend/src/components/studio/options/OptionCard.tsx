import { studioUi } from '../../../content/studio'
import type { ArchitectureOption, Coverage, ProjectBrief, ResearchSnapshot } from '../../../lib/api/types'
import { ELIGIBILITY_LABEL, decidedByModel, receiptsById, summarise, verdictsById } from '../../../lib/decisions'
import { mix, versionLabel, warnings } from '../../../lib/options'
import { safeHref } from '../../../lib/research'
import { DecisionBadge, RulesBadge } from '../DecisionBadge'
import { MermaidDiagram } from './MermaidDiagram'

const COVERAGE_LABEL: Record<Coverage, string> = { covered: 'Covered', partial: 'Partly', not_covered: 'Not covered', unknown: 'Unknown' }
const COVERAGE_STYLE: Record<Coverage, string> = {
  covered: 'bg-chalk text-void',
  partial: 'border border-line text-chalk/85',
  not_covered: 'border border-vermilion text-vermilion',
  unknown: 'border border-dashed border-slate text-smoke',
}

const SECTIONS: { key: 'integration_boundaries' | 'data_flow' | 'storage_model' | 'deployment' | 'security_privacy' | 'testing_approach'; label: string }[] = [
  { key: 'integration_boundaries', label: 'Integration boundaries' },
  { key: 'data_flow', label: 'Data flow' },
  { key: 'storage_model', label: 'Storage' },
  { key: 'deployment', label: 'Deployment' },
  { key: 'security_privacy', label: 'Security and privacy' },
  { key: 'testing_approach', label: 'Testing' },
]

function Heading({ children }: { children: string }) {
  return <h4 className="font-code text-label uppercase text-smoke">{children}</h4>
}

interface OptionCardProps {
  option: ArchitectureOption
  research: ResearchSnapshot | null
  brief: ProjectBrief | null
  /** True for a version that is not the one on offer any more (an older version, looked at). */
  older?: boolean
}

/**
 * One option version, in full. The parts it REUSES carry the same badges as the shortlist: RULES (the gate's
 * verdict) and, where the decision model was asked, LAYA with what it said about that part. The model that drafted
 * the option never gets to set those; they are copied from what was researched.
 */
export function OptionCard({ option, research, brief, older = false }: OptionCardProps) {
  const components = new Map((research?.components ?? []).map((c) => [c.id, c]))
  const verdicts = verdictsById(research?.eligibility ?? [])
  const receipts = receiptsById(research?.receipts ?? [])
  const evidence = new Map((research?.evidence ?? []).map((e) => [e.id, e]))
  const counts = mix(option)
  const checked = option.review
  const requirement = new Map([...(brief?.must_have ?? []), ...(brief?.nice_to_have ?? [])].map((r) => [r.id, r.text]))
  const fixture = option.summary.startsWith('FIXTURE')

  return (
    <article aria-label={option.name} className="flex flex-col gap-32">
      <header className="flex flex-col gap-12">
        <p className="flex flex-wrap items-center gap-10 font-code text-label uppercase text-smoke">
          <span>{versionLabel(option)}</span>
          {option.approved && <span className="rounded-pill bg-chalk px-10 py-2 text-void">{studioUi.options.approved}</span>}
          {older && <span className="rounded-pill border border-line px-10 py-2">older version</span>}
          <span>
            {counts.reuse} reused · {counts.build} built
          </span>
        </p>
        <h3 className="text-h3 font-bold text-chalk md:text-h2">{option.name}</h3>
        {option.trade_off && <p className="max-w-3xl text-lead text-chalk/90">{option.trade_off}</p>}
        <p className="max-w-3xl text-[15px] leading-[1.6] text-smoke">{option.summary}</p>
        {fixture && <p className="font-code text-label uppercase text-vermilion">{studioUi.options.fixture}</p>}
        {option.change_summary && (
          <div className="max-w-3xl border-l-2 border-vermilion py-4 pl-16">
            <p className="font-code text-label uppercase text-vermilion">{studioUi.options.changed}</p>
            <p className="mt-6 text-[16px] leading-[1.6] text-chalk">{option.change_summary}</p>
          </div>
        )}
        {checked && (
          <p className="font-code text-label uppercase text-smoke">
            {studioUi.options.review}: {checked.llm_checked ? studioUi.options.reviewModel : studioUi.options.reviewRulesOnly}
          </p>
        )}
      </header>

      {/* Components */}
      <section className="flex flex-col gap-12">
        <Heading>{studioUi.options.components}</Heading>
        <ul className="border-t border-line">
          {option.components.map((part, index) => {
            const source = part.candidate_id ? components.get(part.candidate_id) : undefined
            const verdict = part.candidate_id ? verdicts.get(part.candidate_id) : undefined
            const decision = part.candidate_id ? summarise(receipts.get(part.candidate_id) ?? []) : null
            const href = source ? safeHref(source.facts.url) : null
            return (
              <li key={`${part.name}-${index}`} className="grid gap-8 border-b border-line py-16 md:grid-cols-[110px_1fr]">
                <span className={`h-24 w-fit rounded-pill px-10 font-code text-[11px] leading-[24px] uppercase ${part.kind === 'reuse' ? 'bg-chalk text-void' : 'border border-line text-chalk/85'}`}>
                  {part.kind === 'reuse' ? studioUi.options.reuse : studioUi.options.build}
                </span>
                <div className="min-w-0">
                  <p className="text-[17px] font-semibold text-chalk">{part.name}</p>
                  <p className="mt-4 text-[15px] leading-[1.6] text-smoke">{part.responsibility}</p>
                  {part.kind === 'reuse' && (
                    <div className="mt-10 flex flex-col gap-8">
                      <p className="font-code text-[13px] break-all text-chalk/85">
                        {href ? (
                          <a href={href} target="_blank" rel="noopener noreferrer" className="underline decoration-line decoration-2 underline-offset-[5px] hover:decoration-vermilion">
                            {part.repo}
                          </a>
                        ) : (
                          part.repo
                        )}
                      </p>
                      {/* Who said what about this reused part: the gate, and the decision model. */}
                      <p className="flex flex-wrap items-center gap-x-10 gap-y-6 text-[13px] text-smoke">
                        {decidedByModel(verdict) && decision ? <DecisionBadge engine={decision.source} /> : <RulesBadge />}
                        <span className="text-chalk/85">{verdict ? ELIGIBILITY_LABEL[verdict.status] : 'not assessed'}</span>
                        <span aria-hidden="true">·</span>
                        {decision ? (
                          <>
                            <DecisionBadge engine={decision.source} />
                            <span className="text-chalk/85">
                              {decision.evaluated
                                ? [decision.fit.join(', '), decision.risk && `${decision.risk} risk`, decision.needsReview && 'check it yourself'].filter(Boolean).join(' · ')
                                : 'could not be asked'}
                            </span>
                          </>
                        ) : (
                          <span>not asked</span>
                        )}
                      </p>
                    </div>
                  )}
                </div>
              </li>
            )
          })}
        </ul>
      </section>

      {/* Pros and cons */}
      <section className="grid gap-24 md:grid-cols-2">
        <div className="flex flex-col gap-10">
          <Heading>{studioUi.options.pros}</Heading>
          <ul className="flex flex-col gap-8">
            {option.pros.map((item) => (
              <li key={item} className="flex gap-10 text-[15px] leading-[1.6] text-chalk/90">
                <span aria-hidden="true" className="text-chalk">+</span>
                {item}
              </li>
            ))}
          </ul>
        </div>
        <div className="flex flex-col gap-10">
          <Heading>{studioUi.options.cons}</Heading>
          <ul className="flex flex-col gap-8">
            {option.cons.map((item) => (
              <li key={item} className="flex gap-10 text-[15px] leading-[1.6] text-chalk/90">
                <span aria-hidden="true" className="text-vermilion">−</span>
                {item}
              </li>
            ))}
          </ul>
        </div>
      </section>

      {(option.choose_if || option.avoid_if) && (
        <section className="grid gap-24 md:grid-cols-2">
          {option.choose_if && (
            <div className="flex flex-col gap-6">
              <Heading>{studioUi.options.chooseIf}</Heading>
              <p className="text-[15px] leading-[1.6] text-chalk/90">{option.choose_if}</p>
            </div>
          )}
          {option.avoid_if && (
            <div className="flex flex-col gap-6">
              <Heading>{studioUi.options.avoidIf}</Heading>
              <p className="text-[15px] leading-[1.6] text-chalk/90">{option.avoid_if}</p>
            </div>
          )}
        </section>
      )}

      {/* The brief's requirements, and how well this option covers each */}
      {Object.keys(option.requirement_coverage).length > 0 && (
        <section className="flex flex-col gap-12">
          <Heading>{studioUi.options.coverage}</Heading>
          <ul className="border-t border-line">
            {Object.entries(option.requirement_coverage).map(([id, coverage]) => (
              <li key={id} className="grid gap-8 border-b border-line py-12 md:grid-cols-[100px_1fr_130px] md:items-baseline">
                <span className="font-code text-[12px] text-smoke">
                  {id}
                  <span className="sr-only">: </span>
                </span>
                <span className="text-[15px] leading-[1.6] text-chalk/90">
                  {requirement.get(id) ?? id}
                  {option.coverage_notes[id] && <span className="mt-4 block text-[13px] text-smoke">{option.coverage_notes[id]}</span>}
                  <span className="sr-only"> — </span>
                </span>
                <span className={`inline-flex h-22 w-fit items-center rounded-pill px-10 font-code text-[11px] uppercase ${COVERAGE_STYLE[coverage]}`}>{COVERAGE_LABEL[coverage]}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {option.mermaid && (
        <section className="flex flex-col gap-12">
          <Heading>{studioUi.options.diagram}</Heading>
          <MermaidDiagram source={option.mermaid} label={`${studioUi.options.diagram}: ${option.name}`} />
        </section>
      )}

      {SECTIONS.some(({ key }) => option[key]) && (
        <section className="flex flex-col gap-12">
          <Heading>{studioUi.options.sections}</Heading>
          <dl className="grid gap-x-32 gap-y-20 md:grid-cols-2">
            {SECTIONS.filter(({ key }) => option[key]).map(({ key, label }) => (
              <div key={key}>
                <dt className="text-[14px] font-semibold text-chalk">{label}</dt>
                <dd className="mt-4 text-[15px] leading-[1.6] text-smoke">{option[key]}</dd>
              </div>
            ))}
          </dl>
        </section>
      )}

      {option.risks.length > 0 && (
        <section className="flex flex-col gap-10">
          <Heading>{studioUi.options.risks}</Heading>
          <ul className="flex flex-col gap-8">
            {option.risks.map((risk) => (
              <li key={risk} className="text-[15px] leading-[1.6] text-chalk/90">
                {risk}
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Validation tasks: claims the evidence does not show. Dashed, because they are tasks, not facts. */}
      {option.validation_tasks.length > 0 && (
        <section className="flex flex-col gap-10 rounded-card border border-dashed border-slate p-16">
          <Heading>{studioUi.options.toValidate}</Heading>
          <p className="text-[13px] text-smoke">{studioUi.options.toValidateHint}</p>
          <ul className="flex flex-col gap-8">
            {option.validation_tasks.map((task) => (
              <li key={task} className="flex gap-10 text-[15px] leading-[1.6] text-chalk/90">
                <span aria-hidden="true" className="text-smoke">☐</span>
                {task}
              </li>
            ))}
          </ul>
        </section>
      )}

      {warnings(option).length > 0 && (
        <section className="flex flex-col gap-10">
          <Heading>{studioUi.options.warnings}</Heading>
          <ul className="flex flex-col gap-6">
            {warnings(option).map((issue, index) => (
              <li key={index} className="text-[14px] leading-[1.6] text-smoke">
                <span className="font-code text-[11px] uppercase">{issue.source === 'rules' ? 'rules' : 'model'}</span> · {issue.text}
              </li>
            ))}
          </ul>
        </section>
      )}

      {option.evidence_ids.length > 0 && (
        <section className="flex flex-col gap-10">
          <Heading>{studioUi.options.evidence}</Heading>
          <ul className="flex flex-wrap gap-8">
            {option.evidence_ids.map((id, index) => {
              const item = evidence.get(id)
              const href = item ? safeHref(item.url) : null
              return (
                <li key={id}>
                  {href ? (
                    <a
                      href={href}
                      target="_blank"
                      rel="noopener noreferrer"
                      title={item?.excerpt ?? item?.url}
                      className="inline-flex h-28 items-center rounded-control border border-line px-12 text-[13px] text-chalk hover:bg-soot focus-visible:outline-2 focus-visible:outline-vermilion"
                    >
                      {studioUi.options.evidence} {index + 1}
                    </a>
                  ) : (
                    <span className="inline-flex h-28 items-center rounded-control border border-dashed border-slate px-12 text-[13px] text-smoke">
                      {studioUi.options.evidence} {index + 1}
                    </span>
                  )}
                </li>
              )
            })}
          </ul>
        </section>
      )}
    </article>
  )
}
