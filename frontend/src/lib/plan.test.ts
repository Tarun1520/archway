import { describe, expect, it } from 'vitest'
import type { PlanSnapshot, RunSnapshot } from './api/types'
import { planPhase } from './plan'
import { currentStage } from './stage'

const plan = (over: Partial<PlanSnapshot> = {}): PlanSnapshot => ({
  requested: true, built_for: { id: 'OPT-1', version: 1 }, approved: { id: 'OPT-1', version: 1 }, stale: false,
  roadmap: null, files: [], links: [], passed: null, outcome: null, notes: [], completed: [], ...over,
})
const run = (over: Partial<RunSnapshot> = {}) =>
  ({ running: false, finished: true, waiting_for: null, brief: { confirmed: true }, ...over }) as unknown as RunSnapshot

describe('planPhase', () => {
  it('follows the real state: nothing asked, making, stopped on an error, ready', () => {
    expect(planPhase(run(), null)).toBe('none')
    expect(planPhase(run(), plan({ requested: false }))).toBe('none')
    expect(planPhase(run({ running: true }), plan())).toBe('making')
    expect(planPhase(run({ running: false }), plan())).toBe('stopped')
    expect(planPhase(run(), plan({ outcome: 'partial', passed: false }))).toBe('ready')
  })
})

describe('the Plan step', () => {
  it('is the current step once a plan is asked for the version approved now', () => {
    expect(currentStage(run(), null, null, plan())).toBe('plan')
  })

  it('is not, when the plan was made for an older version: the new version is on the Options step', () => {
    const options = { requested: true } as never
    expect(currentStage(run(), null, options, plan({ stale: true }))).toBe('options')
  })

  it('never hides a pause for the person', () => {
    const waiting = run({ waiting_for: { node: 'approve_version', payload: {} } as never })
    expect(currentStage(waiting, null, { requested: true } as never, plan())).toBe('options')
  })
})
