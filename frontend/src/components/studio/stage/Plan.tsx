import { useState } from 'react'
import { studioUi } from '../../../content/studio'
import { planExportUrl } from '../../../lib/api/client'
import type { PlanSnapshot, PromptFile, RunSnapshot } from '../../../lib/api/types'
import { planPhase, stageTitle } from '../../../lib/plan'
import { safeHref } from '../../../lib/research'
import type { FeedLine } from '../../../lib/workflowProgress'
import { StudioButton } from '../StudioButton'
import { PlanFlow } from '../plan/PlanFlow'

interface PlanProps {
  run: RunSnapshot | null
  plan: PlanSnapshot | null
  feed: FeedLine[]
  working: boolean
  /** Looking back: nothing here can be changed. */
  readOnly?: boolean
  onRetry: () => void
  onMarkDone: (path: string, done: boolean) => void
}

const copy = studioUi.plan

/**
 * The Plan step (Phase 6). It follows the run's real state (lib/plan.ts `planPhase`):
 *
 *   making    the roadmap is being planned, then the prompts written and checked (live lines from the run)
 *   stopped   planning stopped on an error; it can carry on from where it stopped
 *   ready     the plan: downloads, the roadmap, the prompts to give a coding agent one at a time, the decision
 *             records, and where each requirement goes. A PARTIAL plan says so, with what did not pass.
 */
export function Plan({ run, plan, feed, working, readOnly = false, onRetry, onMarkDone }: PlanProps) {
  const phase = planPhase(run, plan)
  if (phase === 'none' || !plan) return null

  if (phase === 'making') {
    const recent = feed.filter((line) => !line.isError).slice(-4)
    return (
      <section aria-live="polite" className="flex max-w-3xl flex-col gap-16">
        <p className="flex items-center gap-12 text-lead text-chalk">
          <span aria-hidden="true" className="live-dot size-10 rounded-pill bg-vermilion" />
          {copy.making}
        </p>
        <p className="text-[15px] text-smoke">{copy.makingSub}</p>
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

  if (phase === 'stopped') {
    return (
      <div role="alert" className="flex max-w-3xl flex-wrap items-center gap-16 border-l-2 border-vermilion py-8 pl-16">
        <p className="flex-1 text-[16px] text-chalk">{copy.stopped}</p>
        {!readOnly && (
          <StudioButton variant="outline" disabled={working} onClick={onRetry}>
            {studioUi.retry}
          </StudioButton>
        )}
      </div>
    )
  }

  const runId = run?.run.id ?? ''
  const roadmap = plan.roadmap
  const prompts = plan.files.filter((file) => file.kind === 'prompt')
  const context = plan.files.filter((file) => file.kind !== 'prompt')
  const pathOfTask = Object.fromEntries(prompts.flatMap((p) => p.task_ids.map((id) => [id, p.path])))
  const done = new Set(plan.completed)

  return (
    <div className="flex flex-col gap-56">
      {/* What this plan is, whether it passed, and the downloads */}
      <div className={`flex max-w-3xl flex-col gap-16 rounded-card border bg-carbon/80 p-20 ${plan.outcome === 'partial' ? 'border-vermilion/60' : 'border-line'}`}>
        <p className="font-code text-label uppercase text-chalk">
          {copy.builtFor} · {plan.built_for?.id} · version {plan.built_for?.version}
          {' · '}
          <span className={plan.outcome === 'partial' ? 'text-vermilion' : 'text-chalk'}>{plan.outcome === 'partial' ? copy.partial : copy.full}</span>
        </p>
        {plan.outcome === 'partial' && <p className="text-[16px] leading-[1.6] text-smoke">{copy.partialLead}</p>}
        <div className="flex flex-wrap items-center gap-12">
          <span className="font-code text-label uppercase text-smoke">{copy.download}</span>
          {(['zip', 'json', 'md'] as const).map((format) => (
            <a
              key={format}
              href={planExportUrl(runId, format)}
              download
              className="inline-flex min-h-44 items-center rounded-pill border border-line px-16 text-[14px] text-chalk transition-colors hover:bg-soot focus-visible:outline-2 focus-visible:outline-vermilion"
            >
              {format === 'zip' ? copy.zip : format === 'json' ? copy.json : copy.markdown}
            </a>
          ))}
        </div>
        <p className="text-[13px] text-smoke">{copy.review}</p>
      </div>

      {plan.notes.length > 0 && (
        <section className="flex max-w-3xl flex-col gap-12">
          <h3 className="font-code text-label uppercase text-smoke">{copy.notes}</h3>
          <ul className="flex flex-col gap-8">
            {plan.notes.map((note) => (
              <li key={note} className="text-[15px] leading-[1.6] text-chalk/90">
                {note}
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* The whole plan as one animated flow chart */}
      <PlanFlow plan={plan} />

      {/* The prompts: the part the person works through */}
      <section className="flex flex-col gap-20">
        <div className="max-w-3xl">
          <h3 className="text-h3 font-bold text-chalk">{copy.prompts}</h3>
          <p className="mt-8 text-[16px] leading-[1.6] text-smoke">{copy.promptsLead}</p>
        </div>
        <ol className="flex flex-col gap-16">
          {prompts.map((prompt) => (
            <li key={prompt.path}>
              <PromptCard prompt={prompt} done={done} readOnly={readOnly} onMarkDone={onMarkDone} />
            </li>
          ))}
        </ol>
      </section>

      {/* The roadmap */}
      {roadmap && (
        <section className="flex flex-col gap-20">
          <div className="max-w-3xl">
            <h3 className="text-h3 font-bold text-chalk">{copy.tasks}</h3>
            <p className="mt-8 text-[16px] leading-[1.6] text-smoke">{copy.tasksLead}</p>
          </div>
          <ol className="flex flex-col">
            {roadmap.tasks.map((task) => (
              <li key={task.id} className="grid gap-8 border-b border-line py-14 md:grid-cols-[90px_1fr_220px] md:items-baseline">
                <span className="font-code text-[13px] text-smoke">
                  {task.id}
                  <span className="sr-only">: </span>
                </span>
                <span className="flex flex-col gap-4">
                  <span className="text-[16px] font-medium text-chalk">
                    {task.title}
                    {task.kind === 'spike' && (
                      <span title={copy.spikeHint} className="ml-8 inline-flex h-20 items-center rounded-pill border border-[#7fe8ff]/55 px-8 align-middle font-code text-[11px] uppercase tracking-[0.08em] text-[#7fe8ff]">
                        {copy.spike}
                      </span>
                    )}
                  </span>
                  <span className="text-[14px] leading-[1.5] text-smoke">{task.goal}</span>
                  {task.requirement_ids.length > 0 && (
                    <span className="font-code text-[12px] text-chalk/70">
                      {copy.delivers} {task.requirement_ids.join(', ')}
                    </span>
                  )}
                </span>
                <span className="font-code text-[12px] text-smoke">
                  <span className="sr-only"> — </span>
                  {stageTitle(task.stage)} · {task.prerequisites.length > 0 ? `${copy.after} ${task.prerequisites.join(', ')}` : copy.nothingFirst}
                  {pathOfTask[task.id] && <span className="block text-chalk/60">{pathOfTask[task.id]}</span>}
                </span>
              </li>
            ))}
          </ol>
        </section>
      )}

      {/* The decision records */}
      {roadmap && roadmap.decisions.length > 0 && (
        <section className="flex max-w-3xl flex-col gap-16">
          <h3 className="text-h3 font-bold text-chalk">{copy.decisions}</h3>
          {roadmap.decisions.map((decision) => (
            <article key={decision.id} className="flex flex-col gap-8 border-t border-line pt-16">
              <p className="font-code text-label uppercase text-smoke">
                {decision.id} · {decision.source === 'options' ? copy.byOptions : copy.byModel}
              </p>
              <p className="text-[17px] font-semibold text-chalk">{decision.title}</p>
              <p className="text-[15px] leading-[1.6] text-chalk/90">{decision.decision}</p>
              {decision.rejected.length > 0 && (
                <div className="flex flex-col gap-4">
                  <span className="font-code text-[12px] uppercase text-smoke">{copy.rejected}</span>
                  {decision.rejected.map((item) => (
                    <p key={item.option} className="text-[14px] leading-[1.5] text-smoke">
                      <span className="text-chalk/80">{item.option}:</span> {item.why}
                    </p>
                  ))}
                </div>
              )}
            </article>
          ))}
        </section>
      )}

      {/* Source-to-decision links */}
      {plan.links.length > 0 && (
        <details className="max-w-3xl rounded-card border border-line bg-carbon/60 p-20 [&_summary]:cursor-pointer">
          <summary className="text-[17px] font-semibold text-chalk focus-visible:outline-2 focus-visible:outline-vermilion">{copy.links}</summary>
          <p className="mt-8 text-[14px] leading-[1.5] text-smoke">{copy.linksLead}</p>
          <ul className="mt-16 flex flex-col gap-16">
            {plan.links.map((link) => (
              <li key={link.requirement_id} className="flex flex-col gap-6 border-t border-line pt-12">
                <p className="text-[15px] text-chalk">
                  <span className="font-code text-[12px] text-smoke">{link.requirement_id}: </span>
                  {link.requirement}
                </p>
                <p className="font-code text-[12px] text-smoke">
                  {link.coverage} · {link.task_ids.length > 0 ? link.task_ids.join(', ') : '—'}
                </p>
                {link.components.map((part) => (
                  <p key={part.name} className="text-[13px] leading-[1.5] text-chalk/80">
                    {part.name}
                    {part.kind === 'reuse'
                      ? ` · ${part.repo} · ${part.eligibility ?? '?'} (${part.decided_by ? copy.decidedBy[part.decided_by] : '?'}) · ${part.receipt_ids.length} ${copy.receipts}`
                      : ` · ${copy.built}`}
                    {part.evidence.map((item) =>
                      item.url && safeHref(item.url) ? (
                        <a key={item.id} href={safeHref(item.url) ?? undefined} target="_blank" rel="noopener noreferrer" className="ml-8 font-code text-[12px] text-smoke underline decoration-line underline-offset-4 hover:text-chalk">
                          {item.id}
                        </a>
                      ) : (
                        <span key={item.id} className="ml-8 font-code text-[12px] text-smoke">{item.id}</span>
                      ),
                    )}
                  </p>
                ))}
              </li>
            ))}
          </ul>
        </details>
      )}

      {/* The context files of the pack */}
      <details className="max-w-3xl rounded-card border border-line bg-carbon/60 p-20">
        <summary className="cursor-pointer text-[17px] font-semibold text-chalk focus-visible:outline-2 focus-visible:outline-vermilion">{copy.files}</summary>
        <div className="mt-16 flex flex-col gap-12">
          {context.map((file) => (
            <details key={file.path} className="border-t border-line pt-12">
              <summary className="cursor-pointer font-code text-[13px] text-chalk focus-visible:outline-2 focus-visible:outline-vermilion">{file.path}</summary>
              <pre className="mt-8 max-h-[420px] overflow-auto whitespace-pre-wrap rounded-control bg-void/60 p-12 font-code text-[12px] leading-[1.6] text-chalk/85">{file.content}</pre>
            </details>
          ))}
        </div>
      </details>
    </div>
  )
}

function PromptCard({ prompt, done, readOnly, onMarkDone }: { prompt: PromptFile; done: Set<string>; readOnly: boolean; onMarkDone: (path: string, done: boolean) => void }) {
  const [open, setOpen] = useState(false)
  const [copied, setCopied] = useState(false)
  const isDone = done.has(prompt.path)
  const passed = prompt.rubric.filter((check) => check.passed).length
  const failed = prompt.rubric.filter((check) => !check.passed)
  const waitingFor = prompt.prerequisites.filter((path) => !done.has(path))

  const copyPrompt = async () => {
    try {
      await navigator.clipboard.writeText(prompt.content)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1800)
    } catch {
      setOpen(true) // the clipboard is not available: show the text, so it can be selected
    }
  }

  return (
    <article className={`flex flex-col gap-12 rounded-card border p-20 transition-colors ${isDone ? 'border-line bg-carbon/40' : 'border-line bg-carbon/80'}`}>
      <div className="flex flex-wrap items-start justify-between gap-12">
        <div className="flex flex-col gap-4">
          <p className={`text-[18px] font-semibold ${isDone ? 'text-chalk/60 line-through decoration-smoke' : 'text-chalk'}`}>{prompt.title}</p>
          <p className="font-code text-[12px] text-smoke">
            {prompt.path} · {prompt.task_ids.join(', ')}
          </p>
        </div>
        <span className={`inline-flex h-24 items-center rounded-pill border px-10 font-code text-[11px] uppercase tracking-[0.08em] ${failed.length ? 'border-vermilion/60 text-vermilion' : 'border-line text-chalk/80'}`}>
          {passed}/{prompt.rubric.length} {copy.checksPassed}
        </span>
      </div>

      <p className="text-[14px] text-smoke">
        {prompt.prerequisites.length === 0 ? copy.noPrerequisites : `${copy.needsFirst}: `}
        {prompt.prerequisites.map((path, index) => (
          <span key={path} className={done.has(path) ? 'text-chalk/60' : 'text-chalk'}>
            {index > 0 ? ', ' : ''}
            {path.replace('prompts/', '')}
            {done.has(path) ? ' ✓' : ''}
          </span>
        ))}
      </p>

      {failed.length > 0 && (
        <ul className="flex flex-col gap-4 border-l-2 border-vermilion pl-12">
          {failed.map((check) => (
            <li key={check.criterion} className="text-[14px] text-chalk/90">
              {check.criterion}: {check.detail}
            </li>
          ))}
        </ul>
      )}

      <div className="flex flex-wrap items-center gap-12">
        <StudioButton variant="ghost" onClick={() => void copyPrompt()} aria-live="polite">
          {copied ? copy.copied : copy.copy}
        </StudioButton>
        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          aria-expanded={open}
          className="min-h-44 px-4 font-code text-label uppercase text-smoke underline decoration-line decoration-2 underline-offset-[6px] hover:text-chalk focus-visible:outline-2 focus-visible:outline-vermilion"
        >
          {open ? copy.hide : copy.show}
        </button>
        <label className={`ml-auto inline-flex min-h-44 items-center gap-10 text-[14px] ${readOnly ? 'text-smoke' : 'cursor-pointer text-chalk'}`}>
          <input
            type="checkbox"
            checked={isDone}
            disabled={readOnly}
            onChange={(event) => onMarkDone(prompt.path, event.target.checked)}
            className="size-18 accent-[#ff3d00]"
          />
          {isDone ? copy.done : copy.markDone}
          {!isDone && waitingFor.length > 0 && <span className="sr-only"> ({copy.needsFirst}: {waitingFor.join(', ')})</span>}
        </label>
      </div>

      {open && (
        <pre className="max-h-[520px] overflow-auto whitespace-pre-wrap rounded-control bg-void/60 p-12 font-code text-[12px] leading-[1.6] text-chalk/85">{prompt.content}</pre>
      )}
    </article>
  )
}
