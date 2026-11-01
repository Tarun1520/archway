import { useState } from 'react'
import { studioUi, type DetailsTabId } from '../../content/studio'
import type { BriefEdit, PublicConfig, ResearchSnapshot, RunSnapshot, UsageCount } from '../../lib/api/types'
import type { GithubLimitsState } from '../../hooks/useGithubLimits'
import type { FeedLine } from '../../lib/workflowProgress'
import { ActivityFeed } from './ActivityFeed'
import { BriefView } from './BriefView'
import { DecisionsSummary } from './DecisionsSummary'
import { EvidencePanel } from './EvidencePanel'
import { GithubLimitBar } from './GithubLimitBar'
import { ModeBadge } from './ModeBadge'
import { ResearchView } from './ResearchView'

interface DetailsViewProps {
  /** Which section to show (chosen in the nav bar). */
  tab: DetailsTabId
  snapshot: RunSnapshot | null
  research: ResearchSnapshot | null
  feed: FeedLine[]
  config: PublicConfig | null
  githubLimits: GithubLimitsState
  working: boolean
  onApprove: () => void
  onSaveAndApprove: (edit: BriefEdit) => void
}

/**
 * Everything the studio view leaves out, for whoever wants it: the full brief
 * editor, every research find with its judge's notes and the team's
 * conversation, the decision counts, the evidence, the raw activity feed, and
 * usage (model calls, GitHub allowance, live or fixture). The nav bar picks
 * which one is shown.
 */
export function DetailsView({ tab, snapshot, research, feed, config, githubLimits, working, onApprove, onSaveAndApprove }: DetailsViewProps) {
  const [evidenceId, setEvidenceId] = useState<string | null>(null)
  const empty = <p className="py-40 text-lead text-smoke">{studioUi.nothingYet}</p>

  return (
    <div className="flex flex-col gap-32">
      <div id="details-panel">
        <h2 className="mb-24 text-h3 font-bold text-chalk md:text-h2">
          <span data-ripple-anchor="headline">{studioUi.details[tab]}</span>
        </h2>
        {tab === 'brief' &&
          (snapshot?.brief ? (
            <div className="overflow-hidden rounded-card border border-line bg-carbon">
              <BriefView
                key={snapshot.brief.version}
                brief={snapshot.brief}
                runId={snapshot.run.id}
                canDecide={snapshot.waiting_for?.node === 'confirm_brief'}
                working={working}
                onApprove={onApprove}
                onSaveAndApprove={onSaveAndApprove}
              />
            </div>
          ) : (
            empty
          ))}

        {tab === 'research' &&
          (research && research.capabilities.length > 0 ? (
            <div className="overflow-hidden rounded-card border border-line bg-carbon">
              <ResearchView research={research} working={working} selectedEvidenceId={evidenceId} onSelectEvidence={setEvidenceId} />
            </div>
          ) : (
            empty
          ))}

        {tab === 'decisions' &&
          (research && (research.eligibility ?? []).length > 0 ? (
            <DecisionsSummary eligibility={research.eligibility} receipts={research.receipts} components={research.components} />
          ) : (
            empty
          ))}

        {tab === 'evidence' && (
          <div className="overflow-hidden rounded-card border border-line bg-carbon">
            <EvidencePanel evidence={research?.evidence ?? []} selectedId={evidenceId} onSelect={setEvidenceId} />
          </div>
        )}

        {tab === 'activity' && (
          <div className="max-h-[70vh] overflow-y-auto rounded-card border border-line bg-carbon">
            <ActivityFeed lines={feed} hasRun={snapshot !== null} />
          </div>
        )}

        {tab === 'usage' && <Usage usage={snapshot?.usage ?? null} config={config} githubLimits={githubLimits} />}
      </div>
    </div>
  )
}

function Usage({ usage, config, githubLimits }: { usage: UsageCount[] | null; config: PublicConfig | null; githubLimits: GithubLimitsState }) {
  const caps: Record<string, number | null> = {
    llm: config?.caps.max_llm_calls_per_run ?? null,
    jev: config?.caps.max_jev_calls_per_run ?? null,
    github: config?.caps.max_github_calls_per_run ?? null,
  }
  const names: Record<string, string> = { llm: 'Model calls', jev: 'Decisions', github: 'GitHub requests' }
  return (
    <div className="flex flex-col gap-32">
      <dl className="grid grid-cols-1 border-t border-line sm:grid-cols-3">
        {(['llm', 'jev', 'github'] as const).map((service) => {
          const calls = usage?.find((u) => u.service === service)?.calls ?? null
          return (
            <div key={service} className="border-b border-line py-20 pr-16">
              <dt className="font-code text-label uppercase text-smoke">{names[service]}</dt>
              <dd className="mt-6 font-code text-h2 font-semibold text-chalk">
                {calls ?? '—'}
                {caps[service] !== null && <span className="text-h3 text-smoke"> / {caps[service]}</span>}
              </dd>
            </div>
          )
        })}
      </dl>
      <GithubLimitBar state={githubLimits} />
      {config && <ModeBadge modes={config.modes} />}
    </div>
  )
}
