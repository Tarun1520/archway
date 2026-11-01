import { describe, expect, it } from 'vitest'
import type { StreamEvent } from './api/types'
import { progressFromEvents } from './workflowProgress'

let nextId = 0
const event = (name: string, data: StreamEvent['data'] = {}): StreamEvent => ({ id: String(++nextId), name, data })

describe('progressFromEvents', () => {
  it('shows every step as idle when nothing has happened', () => {
    const progress = progressFromEvents([])
    expect(Object.values(progress.nodes).every((status) => status === 'idle')).toBe(true)
    expect(progress.feed).toEqual([])
    expect(progress.researchVersion).toBe(0)
  })

  it('follows the real transitions of a run', () => {
    const progress = progressFromEvents([
      event('run_started'),
      event('node_started', { node: 'intake' }),
      event('activity', { message: 'Intake: brief version 1 drafted' }),
      event('node_finished', { node: 'intake' }),
      event('node_waiting', { node: 'clarify' }),
    ])
    expect(progress.nodes).toMatchObject({ intake: 'done', clarify: 'waiting', confirm_brief: 'idle' })
    expect(progress.feed.map((line) => line.text)).toEqual([
      'Run started',
      'Intake: brief version 1 drafted',
      'Read idea: finished',
      'Ask questions: waiting for you',
    ])
  })

  it('marks an error, stops the working step, and clears the error on retry', () => {
    const failed = [event('run_started'), event('node_started', { node: 'intake' }), event('run_error', { message: 'HTTP 503' })]
    const progress = progressFromEvents(failed)
    expect(progress.error).toBe('HTTP 503')
    expect(progress.nodes.intake).toBe('idle')
    expect(progress.feed.at(-1)).toMatchObject({ text: 'HTTP 503', isError: true })

    const retried = progressFromEvents([...failed, event('run_resumed'), event('node_started', { node: 'intake' })])
    expect(retried.error).toBeNull()
    expect(retried.nodes.intake).toBe('active')
  })

  it('knows when the workflow has finished', () => {
    const progress = progressFromEvents([event('node_finished', { node: 'confirm_brief' }), event('workflow_finished', { message: 'Brief confirmed.' })])
    expect(progress.finished).toBe(true)
    expect(progress.nodes.confirm_brief).toBe('done')
  })

  it('keeps a parallel agent working until every copy has finished', () => {
    const started = Array.from({ length: 3 }, () => event('node_started', { node: 'component_scout' }))
    const midway = progressFromEvents([...started, event('node_finished', { node: 'component_scout' })])
    expect(midway.nodes.component_scout).toBe('active')

    const done = progressFromEvents([...started, ...started.map(() => event('node_finished', { node: 'component_scout' }))])
    expect(done.nodes.component_scout).toBe('done')
    expect(done.feed.filter((line) => line.text.includes('Component scouts: finished'))).toHaveLength(0)
  })

  it('shows what the agents say to each other', () => {
    const progress = progressFromEvents([
      event('team_message', { sender: 'research_lead', recipient: 'capability_analyst', message: 'List the capabilities.' }),
    ])
    expect(progress.feed[0].text).toBe('Research lead → Capability analyst: List the capabilities.')
    expect(progress.researchVersion).toBe(1)
  })

  it('tells GitHub requests apart from model calls and counts research events', () => {
    const progress = progressFromEvents([
      event('usage', { service: 'github', mode: 'live' }),
      event('usage', { service: 'llm', mode: 'live' }),
      event('components_proposed', {}),
    ])
    expect(progress.feed.map((line) => line.text)).toEqual(['GitHub request made (live)', 'Model call made (live)'])
    expect(progress.researchVersion).toBe(1)
  })

  it('ignores event names it does not know', () => {
    expect(progressFromEvents([event('something_new', { node: 'intake' })]).nodes.intake).toBe('idle')
  })
})
