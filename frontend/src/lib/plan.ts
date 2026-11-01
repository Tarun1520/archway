/**
 * Small helpers for the Plan step (Phase 6), from real state only.
 *
 *   planPhase   which view the Plan step shows:
 *                 none      no plan asked for
 *                 making    asked for, being planned, written and checked (the run is working)
 *                 stopped   asked for, not finished, and the run is not working: it stopped on an error
 *                 ready     exported (full or partial)
 *   stageTitle  the plain name of a prompt stage
 */
import type { PlanSnapshot, PlanStage, RunSnapshot } from './api/types'

export type PlanPhase = 'none' | 'making' | 'stopped' | 'ready'

export function planPhase(run: RunSnapshot | null, plan: PlanSnapshot | null): PlanPhase {
  if (!plan?.requested) return 'none'
  if (plan.outcome) return 'ready'
  return run?.running ? 'making' : 'stopped'
}

const STAGE_TITLES: Record<PlanStage, string> = {
  scaffold: 'Scaffold',
  data_and_storage: 'Data and storage',
  backend_features: 'Backend features',
  integrations: 'Integrations',
  frontend: 'Frontend',
  tests_and_security: 'Tests and security',
}

export function stageTitle(stage: PlanStage): string {
  return STAGE_TITLES[stage]
}
