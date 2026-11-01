import { studioCopy } from '../../content/studio'
import type { ResearchSnapshot } from '../../lib/api/types'
import { AlertIcon, CheckIcon } from '../ui/icons'
import { ELIGIBILITY_TIER, receiptsById, verdictsById } from '../../lib/decisions'
import { byRelevance, capabilityTitle, isBuildingBlock } from '../../lib/research'
import { ComponentCard, ProjectCard } from './ComponentCard'
import { TeamConversation } from './TeamConversation'

interface ResearchViewProps {
  research: ResearchSnapshot
  working: boolean
  selectedEvidenceId: string | null
  onSelectEvidence: (id: string) => void
}

function Section({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <section className="rounded-card bg-graphite/60 p-16">
      <h3 className="text-caption font-strong tracking-wide text-ash uppercase">{title}</h3>
      {hint && <p className="mt-4 text-caption text-ash">{hint}</p>}
      <div className="mt-12">{children}</div>
    </section>
  )
}

/**
 * The Research tab: what the agent team found.
 *
 *   1. Capabilities the product needs, each with the approaches to compare,
 *      and the open-source components the scouts proposed for each approach.
 *   2. Similar whole projects (secondary).
 *   3. The reviewer's verdict.
 *   4. The team's conversation: tasks and reports, in order.
 *
 * Everything is the saved research (GET /api/runs/{id}/research). An approach
 * with no component says so; nothing is filled in to look complete.
 */
export function ResearchView({ research, working, selectedEvidenceId, onSelectEvidence }: ResearchViewProps) {
  const { capabilities, components, projects, review, messages, notes } = research
  // Phase 4: the gate's verdicts and the decision receipts, by component.
  const verdicts = verdictsById(research.eligibility ?? [])
  const receipts = receiptsById(research.receipts ?? [])
  // Eligibility tier FIRST (the invariant: nothing outranks an eligible option), then relevance.
  const byTierThenRelevance = (a: (typeof components)[number], b: (typeof components)[number]) => {
    const tier = (c: (typeof components)[number]) => ELIGIBILITY_TIER[verdicts.get(c.id)?.status ?? 'eligible']
    return tier(a) - tier(b) || byRelevance(a, b)
  }

  return (
    <div className="flex flex-col gap-12 overflow-y-auto p-20">
      <header className="flex flex-wrap items-center gap-12">
        <h2 className="text-body-lg font-strong text-ivory">{studioCopy.researchHeading}</h2>
        <span className="inline-flex items-center gap-6 text-caption text-ivory">
          {research.finished ? <CheckIcon size={14} /> : null}
          {research.finished ? studioCopy.researchFinishedLabel : working ? studioCopy.researchWorking : studioCopy.researchIncomplete}
        </span>
        {research.mode === 'fixture' && (
          <span className="inline-flex h-24 items-center rounded-default border border-ivory/50 px-8 font-mono text-caption text-ivory">
            {studioCopy.fixtureData}
          </span>
        )}
      </header>
      <p className="max-w-640 text-body-sm text-ash">{studioCopy.researchIntro}</p>
      {research.mode === 'fixture' && <p className="text-body-sm text-ash">{studioCopy.fixtureResearchNote}</p>}

      {notes.length > 0 && (
        <section role="alert" className="rounded-card border border-ivory bg-obsidian p-16">
          <h3 className="flex items-center gap-8 text-caption font-strong tracking-wide text-ivory uppercase">
            <AlertIcon size={16} /> {studioCopy.researchNotes} ({notes.length})
          </h3>
          <ul className="mt-8 ml-16 list-disc text-body-sm text-ivory">
            {notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </section>
      )}

      {capabilities.length === 0 && (
        <p className="text-body-sm text-ash italic">{working ? studioCopy.researchWorking : studioCopy.researchNoCapabilities}</p>
      )}

      {/* Core capabilities (the product's central job) first, then supporting ones. */}
      {[...capabilities].sort((a, b) => Number(a.priority === 'supporting') - Number(b.priority === 'supporting')).map((capability) => {
        const all = components.filter((component) => component.capability_id === capability.id)
        // Reference-only components are kept, but shown apart and not counted as covering an approach.
        const options = all.filter(isBuildingBlock).sort(byTierThenRelevance)
        const references = all.filter((component) => !isBuildingBlock(component)).sort(byRelevance)
        const gaps = review?.gaps.filter((gap) => gap.capability_id === capability.id) ?? []
        return (
          <Section
            key={capability.id}
            title={`${capability.priority === 'supporting' ? 'Supporting' : 'Core'} · ${capability.id} · ${capabilityTitle(capability.name)}`}
            hint={capability.need}
          >
            {capability.requirement_ids.length > 0 && (
              <p className="mb-12 font-mono text-caption text-ash">
                {studioCopy.serves}: {capability.requirement_ids.join(', ')}
              </p>
            )}
            <div className="flex flex-col gap-16">
              {capability.approaches.map((approach) => {
                const matching = options.filter((option) => option.approach === approach)
                return (
                  <div key={approach} className="flex flex-col gap-8">
                    <h4 className="text-body-sm font-strong text-ivory">
                      {studioCopy.approach}: {approach} <span className="font-normal text-ash">({matching.length})</span>
                    </h4>
                    {matching.length === 0 ? (
                      <p className="text-caption text-ash italic">{studioCopy.noOptionForApproach}</p>
                    ) : (
                      <div className="grid gap-12 xl:grid-cols-2">
                        {matching.map((component) => (
                          <ComponentCard key={component.id} component={component} selectedEvidenceId={selectedEvidenceId} onSelectEvidence={onSelectEvidence} eligibility={verdicts.get(component.id)} receipts={receipts.get(component.id)} />
                        ))}
                      </div>
                    )}
                  </div>
                )
              })}
              {options.some((option) => !option.approach || !capability.approaches.includes(option.approach)) && (
                <div className="flex flex-col gap-8">
                  <h4 className="text-body-sm font-strong text-ivory">{studioCopy.otherOptions}</h4>
                  <div className="grid gap-12 xl:grid-cols-2">
                    {options
                      .filter((option) => !option.approach || !capability.approaches.includes(option.approach))
                      .map((component) => (
                        <ComponentCard key={component.id} component={component} selectedEvidenceId={selectedEvidenceId} onSelectEvidence={onSelectEvidence} eligibility={verdicts.get(component.id)} receipts={receipts.get(component.id)} />
                      ))}
                  </div>
                </div>
              )}
              {references.length > 0 && (
                <details className="rounded-default border border-mist/15 p-12">
                  <summary className="cursor-pointer text-body-sm font-strong text-ivory">
                    Reference only ({references.length}){' '}
                    <span className="font-normal text-ash">
                      finished apps and demos the judge found worth studying, not building blocks
                    </span>
                  </summary>
                  <div className="mt-12 grid gap-12 xl:grid-cols-2">
                    {references.map((component) => (
                      <ComponentCard key={component.id} component={component} selectedEvidenceId={selectedEvidenceId} onSelectEvidence={onSelectEvidence} eligibility={verdicts.get(component.id)} receipts={receipts.get(component.id)} />
                    ))}
                  </div>
                </details>
              )}
              {gaps.length > 0 && (
                <ul className="ml-16 list-disc text-caption text-ivory" aria-label={studioCopy.reviewGaps}>
                  {gaps.map((gap) => (
                    <li key={gap.missing}>
                      {studioCopy.reviewGapLabel}: {gap.missing}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </Section>
        )
      })}

      {projects.length > 0 && (
        <Section title={`${studioCopy.similarProjects} (${projects.length})`} hint={studioCopy.similarProjectsHint}>
          <div className="grid gap-12 xl:grid-cols-2">
            {projects.map((project) => (
              <ProjectCard key={project.name} project={project} selectedEvidenceId={selectedEvidenceId} onSelectEvidence={onSelectEvidence} />
            ))}
          </div>
        </Section>
      )}

      {review && (
        <Section title={studioCopy.reviewHeading}>
          <p className="flex items-center gap-8 text-body-sm text-ivory">
            {review.complete ? <CheckIcon size={14} /> : <AlertIcon size={14} />}
            {review.complete ? studioCopy.reviewComplete : studioCopy.reviewGapsFound}
          </p>
          {review.notes && <p className="mt-8 text-body-sm text-ash">{review.notes}</p>}
        </Section>
      )}

      <Section title={`${studioCopy.teamHeading} (${messages.length})`} hint={studioCopy.teamHint}>
        <TeamConversation messages={messages} />
      </Section>
    </div>
  )
}
