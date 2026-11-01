import { describe, expect, it } from 'vitest'
import type { ResearchSnapshot, RunSnapshot } from './api/types'
import { currentStage } from './stage'

const run = (over: Partial<RunSnapshot>) => ({ waiting_for: null, finished: false, brief: null, ...over }) as unknown as RunSnapshot

describe('currentStage', () => {
  it('follows the run from idea to shortlist', () => {
    expect(currentStage(null, null)).toBe('idea')
    expect(currentStage(run({ waiting_for: { node: 'clarify', payload: {} } as RunSnapshot['waiting_for'] }), null)).toBe('questions')
    expect(currentStage(run({ waiting_for: { node: 'confirm_brief', payload: {} } as RunSnapshot['waiting_for'] }), null)).toBe('brief')
    const confirmed = { confirmed: true } as RunSnapshot['brief']
    expect(currentStage(run({ brief: confirmed }), null)).toBe('research')
    expect(currentStage(run({ brief: confirmed, finished: true }), { finished: true } as ResearchSnapshot)).toBe('shortlist')
  })
})

describe('currentStage: options', () => {
  const confirmed = { confirmed: true } as RunSnapshot['brief']
  const options = (over: object) => ({ requested: false, ...over }) as import('./api/types').OptionsSnapshot

  it('stays at the shortlist until options are asked for', () => {
    expect(currentStage(run({ brief: confirmed, finished: true }), { finished: true } as ResearchSnapshot, options({}))).toBe('shortlist')
  })

  it('is the options step from the moment they are asked for, through choosing, approving and approval', () => {
    const done = { finished: true } as ResearchSnapshot
    expect(currentStage(run({ brief: confirmed }), done, options({ requested: true }))).toBe('options')
    expect(currentStage(run({ brief: confirmed, waiting_for: { node: 'select_or_revise', payload: {} } as RunSnapshot['waiting_for'] }), done, options({}))).toBe('options')
    expect(currentStage(run({ brief: confirmed, waiting_for: { node: 'approve_version', payload: {} } as RunSnapshot['waiting_for'] }), done, null)).toBe('options')
    expect(currentStage(run({ brief: confirmed, finished: true }), done, options({ requested: true, approved: { id: 'OPT-1', version: 1 } }))).toBe('options')
  })
})
