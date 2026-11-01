/**
 * Which of the six steps a project is on, from real state only.
 *
 *   no run yet                          idea
 *   paused for questions                questions
 *   paused for brief approval           brief
 *   finished with research done         shortlist
 *   options asked for (drafting, or     options
 *     waiting for a choice or approval, or approved)
 *   a build plan asked for, for the      plan
 *     version approved now
 *   anything else after the brief       research (running, or stopped part-way)
 */
import type { StageId } from '../content/studio'
import type { OptionsSnapshot, PlanSnapshot, ResearchSnapshot, RunSnapshot } from './api/types'

export function currentStage(
  snapshot: RunSnapshot | null, research: ResearchSnapshot | null, options: OptionsSnapshot | null = null, plan: PlanSnapshot | null = null,
): StageId {
  if (!snapshot) return 'idea'
  const waiting = snapshot.waiting_for?.node
  // A plan made for an OLDER version (stale) does not count: the newer version is approved on the Options step,
  // where a new plan can be asked for.
  if (!waiting && plan?.requested && !plan.stale) return 'plan'
  if (waiting === 'clarify') return 'questions'
  if (waiting === 'confirm_brief') return 'brief'
  if (waiting === 'select_or_revise' || waiting === 'approve_version' || options?.requested) return 'options'
  if (snapshot.finished && research?.finished) return 'shortlist'
  if (!snapshot.brief?.confirmed) return 'brief'
  return 'research'
}
