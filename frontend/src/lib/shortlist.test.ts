import { describe, expect, it } from 'vitest'
import type { Capability, ComponentCandidate, EligibilityVerdict } from './api/types'
import { coreFirst, picksFor } from './shortlist'

const comp = (id: string, fit: number | null, stars: number): ComponentCandidate =>
  ({ id, capability_id: 'CAP-1', name: id, fit, facts: { kind: 'github', stars } }) as unknown as ComponentCandidate
const verdict = (id: string, status: EligibilityVerdict['status']): [string, EligibilityVerdict] => [
  id,
  { component_id: id, status, reasons: [], policy_version: 'p' },
]

describe('picksFor', () => {
  it('keeps eligible first, drops demos, excluded and unresolved, and caps at three', () => {
    const components = [comp('demo', 1, 900), comp('gpl', 3, 800), comp('review', 3, 700), comp('a', 2, 10), comp('b', 3, 5), comp('c', 3, 50)]
    const verdicts = new Map([verdict('gpl', 'excluded'), verdict('review', 'review_required'), verdict('a', 'eligible'), verdict('b', 'eligible'), verdict('c', 'eligible')])
    expect(picksFor('CAP-1', components, verdicts).map((p) => p.component.id)).toEqual(['c', 'b', 'a'])
  })
})

describe('coreFirst', () => {
  it('puts core capabilities before supporting ones', () => {
    const caps = [{ id: 'S', priority: 'supporting' }, { id: 'C', priority: 'core' }] as Capability[]
    expect(coreFirst(caps).map((c) => c.id)).toEqual(['C', 'S'])
  })
})
