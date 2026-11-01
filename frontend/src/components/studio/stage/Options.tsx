import { useState } from 'react'
import { studioUi } from '../../../content/studio'
import type { OptionsSnapshot, PlanSnapshot, ResearchSnapshot, RunSnapshot } from '../../../lib/api/types'
import { optionsPhase, presentedOptions, versionsOf, withheld } from '../../../lib/options'
import type { FeedLine } from '../../../lib/workflowProgress'
import { StudioButton } from '../StudioButton'
import { ChangeBox } from '../options/ChangeBox'
import { ComparisonTable } from '../options/ComparisonTable'
import { OptionCard } from '../options/OptionCard'

interface OptionsProps {
  run: RunSnapshot | null
  options: OptionsSnapshot | null
  research: ResearchSnapshot | null
  feed: FeedLine[]
  working: boolean
  /** Looking back from a later step: nothing here can be changed. */
  readOnly?: boolean
  /** The options are ready but the agents are still leaving the stage: keep the drafting view a moment longer. */
  holding?: boolean
  onChoose: (optionId: string) => void
  onRevise: (optionId: string | null, request: string) => void
  onApprove: () => void
  onChangeAtApproval: (request: string) => void
  onChangeApproved: (optionId: string, request: string) => void
  /** Phase 6: the build plan for the approved version (absent when looking back). */
  plan?: PlanSnapshot | null
  onStartPlan?: () => void
  onOpenPlan?: () => void
}

/**
 * The Options step. It follows the run's real state (lib/options.ts `optionsPhase`):
 *
 *   drafting           options are being drafted and reviewed (live lines from the run)
 *   choosing           the options that passed review, side by side; choose one, or ask for a change
 *   no_recommendation  nothing could honestly be recommended: what is missing, and a way to steer a new draft
 *   approving          one version is selected: approve exactly that version, or ask for a change
 *   approved           that version is approved; a later change makes a NEW version that needs its own approval
 */
export function Options({ run, options, research, feed, working, readOnly = false, holding = false, onChoose, onRevise, onApprove, onChangeAtApproval, onChangeApproved, plan = null, onStartPlan, onOpenPlan }: OptionsProps) {
  const phase = optionsPhase(run, options)
  const offered = presentedOptions(options)
  const brief = run?.brief ?? null
  const approvedRef = options?.approved ?? null
  // While waiting for approval, the run itself says which version (so the banner never depends on a reload).
  const waitingPayload = run?.waiting_for?.node === 'approve_version' ? run.waiting_for.payload : null
  const approving = waitingPayload?.option_id ? { id: waitingPayload.option_id, version: waitingPayload.version ?? 1 } : (options?.selected ?? null)
  const selectedRef = phase === 'approving' ? approving : approvedRef
  // The option on screen: the selected or approved one, else the one the person last looked at, else the first.
  const [viewId, setViewId] = useState<string | null>(null)
  const [viewVersion, setViewVersion] = useState<number | null>(null)
  const activeId = viewId && offered.some((o) => o.id === viewId) ? viewId : (selectedRef?.id ?? offered[0]?.id ?? null)
  const versions = activeId ? versionsOf(options, activeId) : []
  const current = offered.find((o) => o.id === activeId) ?? null
  const shown = (viewVersion !== null ? versions.find((o) => o.version === viewVersion) : null) ?? current
  const older = shown !== null && current !== null && shown.version !== current.version
  const pick = (id: string) => {
    setViewId(id)
    setViewVersion(null)
  }

  if (phase === 'none') return null

  if (phase === 'drafting' || holding) {
    const recent = feed.filter((line) => !line.isError).slice(-4)
    return (
      <section aria-live="polite" className="flex max-w-3xl flex-col gap-16">
        <p className="flex items-center gap-12 text-lead text-chalk">
          <span aria-hidden="true" className="live-dot size-10 rounded-pill bg-vermilion" />
          {holding ? studioUi.options.ready : studioUi.options.drafting}
        </p>
        <p className="text-[15px] text-smoke">{holding ? studioUi.options.readySub : studioUi.options.draftingSub}</p>
        <ul className="flex flex-col gap-6 border-l border-line pl-16">
          {recent.map((line) => (
            <li key={line.id} className="text-[14px] text-smoke">
              {line.text}
            </li>
          ))}
        </ul>
      </section>
    )
  }

  const notes = options?.notes ?? []
  const failed = withheld(options)

  return (
    <div className="flex flex-col gap-48">
      {/* The state of the decision, in one banner */}
      {phase === 'approving' && approving && (
        <div className="flex max-w-3xl flex-col gap-16 rounded-card border border-vermilion/60 bg-carbon/80 p-20">
          <p className="font-code text-label uppercase text-vermilion">
            {approving.id} · version {approving.version}
          </p>
          <p className="text-[17px] leading-[1.6] text-chalk">{studioUi.options.approveHint}</p>
          {!readOnly && (
            <div>
              <StudioButton disabled={working} onClick={onApprove}>
                {studioUi.options.approve}
              </StudioButton>
            </div>
          )}
        </div>
      )}
      {phase === 'approved' && approvedRef && (
        <div className="flex max-w-3xl flex-col gap-8 rounded-card border border-line bg-carbon/80 p-20">
          <p className="font-code text-label uppercase text-chalk">
            {studioUi.options.approved} · {approvedRef.id} · version {approvedRef.version}
          </p>
          <p className="text-[16px] leading-[1.6] text-smoke">{plan?.stale ? studioUi.options.stalePlan : studioUi.options.approvedLead}</p>
          {!readOnly && plan?.requested && !plan.stale && onOpenPlan && (
            <div className="mt-8">
              <StudioButton onClick={onOpenPlan}>{studioUi.options.openPlan}</StudioButton>
            </div>
          )}
          {!readOnly && (!plan?.requested || plan.stale) && onStartPlan && (
            <div className="mt-8 flex flex-wrap items-center gap-16">
              <StudioButton disabled={working || run?.running === true} onClick={onStartPlan}>
                {studioUi.options.makePlan}
              </StudioButton>
              <p className="text-[14px] text-smoke">{studioUi.options.makePlanHint}</p>
            </div>
          )}
        </div>
      )}
      {phase === 'no_recommendation' && (
        <div className="flex max-w-3xl flex-col gap-12 border-l-2 border-vermilion py-4 pl-20">
          <p className="text-h3 font-bold text-chalk">{studioUi.options.noRecommendation}</p>
          <p className="text-[16px] leading-[1.6] text-smoke">{studioUi.options.noRecommendationLead}</p>
          <ul className="flex flex-col gap-8">
            {notes.map((note) => (
              <li key={note} className="text-[15px] leading-[1.6] text-chalk/90">
                {note}
              </li>
            ))}
          </ul>
        </div>
      )}

      {offered.length > 1 && <ComparisonTable options={offered} selectedId={activeId} onPick={pick} />}

      {shown && (
        <section className="flex flex-col gap-24">
          {/* Which option, and which version of it */}
          <div className="flex flex-wrap items-center gap-x-24 gap-y-12 border-t border-line pt-24">
            {offered.length > 1 && (
              <div role="tablist" aria-label="Options" className="flex flex-wrap gap-8">
                {offered.map((option) => (
                  <button
                    key={option.id}
                    type="button"
                    role="tab"
                    aria-selected={option.id === activeId}
                    onClick={() => pick(option.id)}
                    className={`h-36 rounded-pill px-16 text-[14px] transition-colors focus-visible:outline-2 focus-visible:outline-vermilion ${
                      option.id === activeId ? 'bg-chalk font-medium text-void' : 'border border-line text-chalk/85 hover:bg-soot'
                    }`}
                  >
                    {option.id} · {option.name.length > 28 ? `${option.name.slice(0, 27)}…` : option.name}
                  </button>
                ))}
              </div>
            )}
            {versions.length > 1 && (
              <div className="flex flex-wrap items-center gap-8" aria-label={studioUi.options.versions}>
                <span className="font-code text-label uppercase text-smoke">{studioUi.options.versions}</span>
                {versions.map((version) => (
                  <button
                    key={version.version}
                    type="button"
                    aria-pressed={version.version === shown.version}
                    onClick={() => setViewVersion(version.version)}
                    className={`h-28 rounded-control px-12 font-code text-[12px] focus-visible:outline-2 focus-visible:outline-vermilion ${
                      version.version === shown.version ? 'bg-soot text-chalk' : 'border border-line text-smoke hover:text-chalk'
                    }`}
                  >
                    v{version.version}
                    {version.approved ? ' ✓' : ''}
                    {version.review && !version.review.passed ? ' ✕' : ''}
                  </button>
                ))}
              </div>
            )}
          </div>

          <OptionCard option={shown} research={research} brief={brief} older={older} />

          {/* What the person can do with the option on screen */}
          {!readOnly && phase === 'choosing' && !older && (
            <div className="flex flex-col gap-24 border-t border-line pt-24">
              <div>
                <StudioButton disabled={working} onClick={() => onChoose(shown.id)}>
                  {studioUi.options.choose}
                </StudioButton>
              </div>
              <ChangeBox working={working} onSend={(request) => onRevise(shown.id, request)} />
            </div>
          )}
          {!readOnly && phase === 'approving' && (
            <div className="border-t border-line pt-24">
              <ChangeBox working={working} onSend={onChangeAtApproval} />
            </div>
          )}
          {!readOnly && phase === 'approved' && approvedRef && (
            <div className="border-t border-line pt-24">
              <ChangeBox working={working} label={studioUi.options.changeApproved} onSend={(request) => onChangeApproved(approvedRef.id, request)} />
            </div>
          )}
        </section>
      )}

      {!readOnly && phase === 'no_recommendation' && <ChangeBox working={working} onSend={(request) => onRevise(null, request)} />}

      {(failed.length > 0 || (notes.length > 0 && phase !== 'no_recommendation')) && (
        <details className="max-w-3xl rounded-card border border-line bg-carbon/60 p-16">
          <summary className="cursor-pointer font-code text-label uppercase text-smoke">{studioUi.options.notes}</summary>
          <ul className="mt-12 flex flex-col gap-8">
            {notes.filter(() => phase !== 'no_recommendation').map((note) => (
              <li key={note} className="text-[14px] leading-[1.6] text-chalk/85">
                {note}
              </li>
            ))}
            {failed.map((option) => (
              <li key={`${option.id}-${option.version}`} className="text-[14px] leading-[1.6] text-chalk/85">
                {studioUi.options.withheldLead} {option.id} v{option.version}: {(option.review?.issues ?? []).filter((i) => i.severity === 'blocking').map((i) => i.text).join('; ') || 'it did not pass review'}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  )
}
