/**
 * The shortlist: for each capability, the few parts worth a first look.
 *
 * Rules, in order: never a finished app or demo (judged reference only), never
 * an excluded or unresolved one; eligible before "review needed"; then by
 * judged fit and adoption (byRelevance). At most three per capability.
 */
import type { Capability, ComponentCandidate, EligibilityVerdict } from './api/types'
import { ELIGIBILITY_TIER } from './decisions'
import { byRelevance, isBuildingBlock } from './research'

export const PICKS_PER_CAPABILITY = 3

export interface Pick {
  component: ComponentCandidate
  verdict: EligibilityVerdict | null
}

export function picksFor(capabilityId: string, components: ComponentCandidate[], verdicts: Map<string, EligibilityVerdict>): Pick[] {
  return components
    .filter((c) => c.capability_id === capabilityId && isBuildingBlock(c))
    .map((component) => ({ component, verdict: verdicts.get(component.id) ?? null }))
    .filter(({ verdict }) => !verdict || verdict.status === 'eligible' || verdict.status === 'review_required')
    .sort((a, b) => {
      const tier = (p: Pick) => ELIGIBILITY_TIER[p.verdict?.status ?? 'eligible']
      return tier(a) - tier(b) || byRelevance(a.component, b.component)
    })
    .slice(0, PICKS_PER_CAPABILITY)
}

/** Core capabilities first, keeping the analyst's order inside each group. */
export function coreFirst(capabilities: Capability[]): Capability[] {
  return [...capabilities].sort((a, b) => Number(a.priority === 'supporting') - Number(b.priority === 'supporting'))
}
