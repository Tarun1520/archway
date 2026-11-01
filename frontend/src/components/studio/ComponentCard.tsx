import { studioCopy } from '../../content/studio'
import type { ComponentCandidate, DecisionReceipt, EligibilityVerdict, SimilarProject } from '../../lib/api/types'
import { ELIGIBILITY_LABEL, decidedByModel, summarise } from '../../lib/decisions'
import { agentLabel, fitView, formatWhen, isLowAdoption, licenseView, safeHref, shortCount } from '../../lib/research'
import { AlertIcon, CheckIcon, SparkleIcon, UnknownIcon } from '../ui/icons'
import { DecisionBadge, RulesBadge } from './DecisionBadge'

const tagClasses = 'inline-flex h-24 items-center gap-6 rounded-default border px-8 text-caption'
const SOURCE_LABEL = { github: 'GitHub', pypi: 'PyPI', npm: 'npm' } as const

interface FactsProps {
  facts: ComponentCandidate['facts']
  selectedEvidenceId: string | null
  onSelectEvidence: (id: string) => void
}

/**
 * The FACTS about a source: copied by code from what the tools retrieved.
 * Shown apart from the agent's claims, with no sparkle, because no model wrote them.
 */
function Facts({ facts, selectedEvidenceId, onSelectEvidence }: FactsProps) {
  const license = licenseView(facts)
  const href = safeHref(facts.url)
  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-wrap gap-6">
        <span className={`${tagClasses} border-mist/25 font-mono text-ivory`}>{SOURCE_LABEL[facts.kind]}</span>
        <span className={`${tagClasses} ${license.kind === 'detected' ? 'border-ivory/50 text-ivory' : 'border-dashed border-ivory/60 text-ivory'}`}>
          {license.kind === 'detected' ? <CheckIcon size={12} /> : <UnknownIcon size={12} />}
          {license.label}
        </span>
        {isLowAdoption(facts) && (
          <span className={`${tagClasses} border-dashed border-ivory/60 text-ivory`} title="Few stars or downloads: check maturity before relying on it.">
            <AlertIcon size={12} /> Low adoption
          </span>
        )}
        {facts.archived === true && (
          <span className={`${tagClasses} border-ivory/60 text-ivory`}>
            <AlertIcon size={12} /> Archived
          </span>
        )}
        {facts.mode === 'fixture' && <span className={`${tagClasses} border-ivory/50 font-mono text-ivory`}>{studioCopy.fixtureData}</span>}
      </div>
      <p className="text-caption text-ash">
        {facts.stars !== null && `${facts.stars.toLocaleString('en-GB')} stars · `}
        {facts.downloads_last_month != null && `${shortCount(facts.downloads_last_month)} downloads/month · `}
        {facts.last_activity ? `${studioCopy.lastActivity} ${formatWhen(facts.last_activity)}` : studioCopy.lastActivityUnknown}
      </p>
      <p className="text-caption break-all text-ash">
        {studioCopy.provenanceSource}:{' '}
        {href ? (
          <a href={href} target="_blank" rel="noopener noreferrer" className="underline decoration-ivory/40 underline-offset-4">
            {facts.reference}
          </a>
        ) : (
          facts.reference
        )}
      </p>
      {facts.evidence_ids.length > 0 && (
        <div className="flex flex-wrap gap-6">
          {facts.evidence_ids.map((id, index) => (
            <button
              key={id}
              type="button"
              aria-pressed={selectedEvidenceId === id}
              onClick={() => onSelectEvidence(id)}
              className={`h-28 rounded-control border px-12 text-caption ${
                selectedEvidenceId === id ? 'border-ivory bg-ivory/10 text-ivory' : 'border-mist/25 text-ivory hover:bg-ivory/10'
              }`}
            >
              {studioCopy.showEvidence} {index + 1}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

interface ComponentCardProps {
  component: ComponentCandidate
  selectedEvidenceId: string | null
  onSelectEvidence: (id: string) => void
  /** Phase 4: the gate's verdict and the decision model's receipts, when they exist. */
  eligibility?: EligibilityVerdict
  receipts?: DecisionReceipt[]
}

/**
 * Phase 4 for one component, with WHO decided each part:
 *   RULES  the deterministic gate's verdict (plain code, no model, last word)
 *   LAYA   the decision model's typed answers, one line per question, with how sure it said it was
 * Live or fixture is always shown beside the model's answers, so a fixture answer is never mistaken for a real one.
 */
function Decision({ eligibility, receipts }: { eligibility?: EligibilityVerdict; receipts: DecisionReceipt[] }) {
  const summary = summarise(receipts)
  if (!eligibility && !summary) return null
  const strong = eligibility?.status === 'eligible'
  const byModel = decidedByModel(eligibility)
  return (
    <section className="flex flex-col gap-10 rounded-default border border-mist/20 p-8" aria-label="Eligibility and decisions">
      {eligibility && (
        <div className="flex flex-col gap-6">
          <p className="flex flex-wrap items-center gap-8">
            {byModel && summary ? <DecisionBadge engine={summary.source} /> : <RulesBadge />}
            <span className={`${tagClasses} ${strong ? 'border-ivory/70' : 'border-dashed border-ivory/60'} text-ivory`}>
              {strong ? <CheckIcon size={12} /> : <AlertIcon size={12} />}
              {ELIGIBILITY_LABEL[eligibility.status]}
            </span>
          </p>
          {eligibility.reasons.length > 0 && <p className="text-caption text-ash">{eligibility.reasons.join('; ')}</p>}
          {byModel && <p className="text-caption text-ash">The decision model's answer, not a plain rule, decided this one.</p>}
        </div>
      )}
      {summary && (
        <div className="flex flex-col gap-6">
          <p className="flex flex-wrap items-center gap-8 text-caption text-ash">
            <DecisionBadge engine={summary.source} />
            <span className="font-mono uppercase">{summary.engine ?? 'decision model'} ({summary.mode})</span>
          </p>
          {summary.evaluated ? (
            <ul className="flex flex-col gap-2">
              {summary.lines.map((line, index) => (
                <li key={index} className="flex flex-wrap items-baseline gap-x-8 text-caption">
                  <span className="text-ash">{line.question}</span>
                  <span className="text-ivory">{line.answer ?? 'not asked'}</span>
                  {line.confidence !== null && (
                    <span className="font-mono text-ash" title="The model's own raw score, not a calibrated chance of being right.">
                      {Math.round(line.confidence * 100)}% score
                    </span>
                  )}
                  {line.needsReview && line.answer !== null && <span className="text-ivory">· unsure: a person should check</span>}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-caption text-ivory">not evaluated: the decision model could not be asked, so nothing was guessed</p>
          )}
        </div>
      )}
    </section>
  )
}

/**
 * One open-source building block a scout proposed.
 *
 * Two halves, kept visibly apart:
 *   - what the AGENT says (sparkle, "suggested by"): what it provides, why it may fit, concerns
 *   - the FACTS (no sparkle): source, license, archived, activity, evidence links
 */
export function ComponentCard({ component, selectedEvidenceId, onSelectEvidence, eligibility, receipts = [] }: ComponentCardProps) {
  const fit = fitView(component)
  return (
    <article className="flex flex-col gap-12 rounded-card bg-obsidian p-16" aria-label={component.name}>
      <header className="flex flex-wrap items-baseline gap-8">
        <h4 className="text-body font-strong break-all text-ivory">{component.name}</h4>
        {component.approach && <span className="text-caption text-ash">{component.approach}</span>}
      </header>

      <section className="flex flex-col gap-6 rounded-default border border-dotted border-ivory/30 p-8" aria-label={studioCopy.agentClaims}>
        <p className="flex items-center gap-6 font-mono text-caption tracking-wide text-ash uppercase">
          <SparkleIcon size={12} /> {studioCopy.suggestedBy} {agentLabel(component.proposed_by)}
        </p>
        <p className="text-body-sm text-ivory">{component.provides}</p>
        <p className="text-body-sm text-ash">{component.fit_notes}</p>
        {component.concerns.length > 0 && (
          <ul className="ml-16 list-disc text-caption text-ivory">
            {component.concerns.map((concern) => (
              <li key={concern}>{concern}</li>
            ))}
          </ul>
        )}
      </section>

      {/* The independent judge saw only the facts below, never the agent's claims above. */}
      {fit && (
        <section className="flex flex-col gap-4 rounded-default border border-dotted border-ivory/30 p-8" aria-label="Independent relevance check">
          <p className="flex flex-wrap items-center gap-6 font-mono text-caption tracking-wide text-ash uppercase">
            <SparkleIcon size={12} /> Independent relevance check
          </p>
          <p className="flex flex-wrap items-center gap-8 text-body-sm text-ivory">
            <span className={`${tagClasses} ${component.fit !== null && component.fit >= 3 ? 'border-ivory/60' : 'border-dashed border-ivory/60'} text-ivory`}>
              {fit.label}
            </span>
            {fit.kind && <span className="text-caption text-ash">{fit.kind}</span>}
          </p>
          {component.fit_reason && <p className="text-caption text-ash">{component.fit_reason}</p>}
        </section>
      )}

      <Decision eligibility={eligibility} receipts={receipts} />

      <Facts facts={component.facts} selectedEvidenceId={selectedEvidenceId} onSelectEvidence={onSelectEvidence} />
    </article>
  )
}

export function ProjectCard({ project, selectedEvidenceId, onSelectEvidence }: { project: SimilarProject } & Omit<FactsProps, 'facts'>) {
  return (
    <article className="flex flex-col gap-10 rounded-card bg-obsidian p-16" aria-label={project.name}>
      <h4 className="text-body font-strong break-all text-ivory">{project.name}</h4>
      <section className="flex flex-col gap-4 rounded-default border border-dotted border-ivory/30 p-8">
        <p className="flex items-center gap-6 font-mono text-caption tracking-wide text-ash uppercase">
          <SparkleIcon size={12} /> {studioCopy.suggestedBy} {agentLabel('project_scout')}
        </p>
        <p className="text-body-sm text-ivory">{project.why_similar}</p>
        <p className="text-body-sm text-ash">{project.worth_learning}</p>
      </section>
      <Facts facts={project.facts} selectedEvidenceId={selectedEvidenceId} onSelectEvidence={onSelectEvidence} />
    </article>
  )
}
