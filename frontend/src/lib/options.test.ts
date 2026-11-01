import { describe, expect, it } from 'vitest'
import type { ArchitectureOption, OptionsSnapshot, RunSnapshot } from './api/types'
import { mix, optionsPhase, presentedOptions, versionsOf, withheld } from './options'

const option = (over: Partial<ArchitectureOption>): ArchitectureOption =>
  ({
    id: 'OPT-1', version: 1, brief_version: 1, name: 'A', trade_off: null, summary: 's', requirement_coverage: {}, coverage_notes: {},
    components: [], reused_repos: [], integration_boundaries: null, data_flow: null, storage_model: null, deployment: null,
    security_privacy: null, testing_approach: null, risks: [], validation_tasks: [], mermaid: null, evidence_ids: [], pros: ['p'], cons: ['c'],
    choose_if: null, avoid_if: null, comparison: [], change_summary: null, review: { passed: true, issues: [], llm_checked: true }, approved: false,
    ...over,
  }) as ArchitectureOption

const snapshot = (over: Partial<OptionsSnapshot>): OptionsSnapshot => ({
  requested: true, options: [], presented: [], selected: null, approved: null, notes: [], no_recommendation: false, ...over,
})

const run = (over: Partial<RunSnapshot>): RunSnapshot => ({ waiting_for: null, finished: false, running: false, ...over }) as RunSnapshot

describe('optionsPhase', () => {
  it('follows what the run is waiting for', () => {
    const waiting = (node: 'select_or_revise' | 'approve_version', payload = {}) => run({ waiting_for: { node, payload } })
    expect(optionsPhase(waiting('select_or_revise', { presented: [{ id: 'OPT-1', version: 1 }] }), snapshot({}))).toBe('choosing')
    expect(optionsPhase(waiting('select_or_revise', { no_recommendation: true }), snapshot({}))).toBe('no_recommendation')
    expect(optionsPhase(waiting('approve_version'), snapshot({}))).toBe('approving')
  })

  it('is drafting while the run works, approved when finished with an approval, stopped after an error', () => {
    expect(optionsPhase(run({ running: true }), snapshot({}))).toBe('drafting')
    expect(optionsPhase(run({ finished: true }), snapshot({ approved: { id: 'OPT-1', version: 1 } }))).toBe('approved')
    expect(optionsPhase(run({}), snapshot({}))).toBe('stopped')
  })

  it('is drafting while the run works, even if the snapshot still shows the pause it just left', () => {
    expect(optionsPhase(run({ running: true, waiting_for: { node: 'select_or_revise', payload: {} } }), snapshot({}))).toBe('drafting')
  })

  it('is none until options were asked for', () => {
    expect(optionsPhase(run({ finished: true }), snapshot({ requested: false }))).toBe('none')
    expect(optionsPhase(null, null)).toBe('none')
  })
})

describe('which versions are shown', () => {
  const v1 = option({ id: 'OPT-1', version: 1 })
  const v2 = option({ id: 'OPT-1', version: 2, review: { passed: false, issues: [{ severity: 'blocking', kind: 'k', text: 't', source: 'rules' }], llm_checked: true } })
  const other = option({ id: 'OPT-2', version: 1, review: { passed: false, issues: [], llm_checked: false } })
  const snap = snapshot({ options: [v1, v2, other], presented: [{ id: 'OPT-1', version: 1 }] })

  it('offers only the versions the backend says passed review', () => {
    expect(presentedOptions(snap)).toEqual([v1])
  })

  it('lists every version of one option, oldest first', () => {
    expect(versionsOf(snap, 'OPT-1').map((o) => o.version)).toEqual([1, 2])
  })

  it('reports options that failed review and were not offered, but not a failed revision of an offered one', () => {
    expect(withheld(snap)).toEqual([other])
  })

  it('counts what is reused and what is built', () => {
    const parts = [{ kind: 'reuse' }, { kind: 'build' }, { kind: 'build' }] as ArchitectureOption['components']
    expect(mix(option({ components: parts }))).toEqual({ reuse: 1, build: 2 })
  })
})
