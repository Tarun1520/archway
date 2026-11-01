import { describe, expect, it } from 'vitest'
import type { StreamEvent } from './api/types'
import { bubbleText, teamFromEvents } from './agentTeam'

let n = 0
const ev = (name: string, data: StreamEvent['data'] = {}): StreamEvent => ({ id: String(++n), name, data })

describe('teamFromEvents', () => {
  it('starts with everyone idle', () => {
    const team = teamFromEvents([])
    expect(team.live).toBe(false)
    expect(team.started).toBe(false)
    expect(team.agents.lead.status).toBe('idle')
  })

  it('shows what each agent is doing from its real tool calls', () => {
    const team = teamFromEvents([
      ev('node_started', { node: 'component_scout' }),
      ev('agent_action', { agent: 'component_scout', tool: 'search_github' }),
    ])
    expect(team.live).toBe(true)
    expect(team.agents.scout).toMatchObject({ status: 'working', doing: 'Searching GitHub', copies: 1 })
  })

  it('keeps parallel scouts working until the last one finishes, and the judge with them', () => {
    const team = teamFromEvents([
      ev('node_started', { node: 'component_scout' }),
      ev('node_started', { node: 'component_scout' }),
      ev('agent_action', { agent: 'relevance_judge', tool: 'submit_fit' }),
      ev('node_finished', { node: 'component_scout' }),
    ])
    expect(team.agents.scout).toMatchObject({ status: 'working', copies: 1 })
    expect(team.agents.judge.status).toBe('working')
    const done = teamFromEvents([
      ev('node_started', { node: 'component_scout' }),
      ev('agent_action', { agent: 'relevance_judge', tool: 'submit_fit' }),
      ev('node_finished', { node: 'component_scout' }),
    ])
    expect(done.agents.scout.status).toBe('done')
    expect(done.agents.judge.status).toBe('done')
  })

  it('records who wrote to whom, newest last, and caps the list', () => {
    const events = Array.from({ length: 8 }, (_, i) =>
      ev('team_message', { sender: 'research_lead', recipient: 'component_scout', message: `task ${i}` }),
    )
    const team = teamFromEvents(events)
    expect(team.messages).toHaveLength(6)
    expect(team.messages.at(-1)).toMatchObject({ from: 'lead', to: 'scout', text: 'task 7' })
  })

  it('treats decision-model usage as Laya working, and an error stops everyone', () => {
    expect(teamFromEvents([ev('usage', { service: 'jev' })]).agents.decider.status).toBe('working')
    const stopped = teamFromEvents([ev('node_started', { node: 'reviewer' }), ev('run_error', { message: 'x' })])
    expect(stopped.live).toBe(false)
    expect(stopped.agents.reviewer.status).toBe('idle')
  })
})

describe('bubbleText', () => {
  it('shortens long messages on a word boundary-ish cut', () => {
    expect(bubbleText('short')).toBe('short')
    expect(bubbleText('a'.repeat(100), 10)).toBe('aaaaaaaaa…')
  })
})

describe('team thoughts', () => {
  it('turns real tool calls into simple first-person thoughts, quoting the subject', () => {
    const team = teamFromEvents([
      ev('node_started', { node: 'component_scout' }),
      ev('agent_action', { agent: 'component_scout', tool: 'search_github', about: 'offline maps', ok: true }),
    ])
    expect(team.agents.scout.thought).toBe('Let me look on GitHub for “offline maps”.')
    expect(team.thoughts.map((t) => t.text)).toEqual([
      'Getting ready to search for my part.',
      'Let me look on GitHub for “offline maps”.',
    ])
  })

  it('uses counts, says plainly when something failed, and shows a repeated thought once', () => {
    const team = teamFromEvents([
      ev('node_started', { node: 'component_scout' }),
      ev('node_started', { node: 'component_scout' }),
      ev('agent_action', { agent: 'capability_analyst', tool: 'record_capabilities', count: 4, ok: true }),
      ev('agent_action', { agent: 'component_scout', tool: 'search_github', about: 'x', ok: false }),
    ])
    const texts = team.thoughts.map((t) => t.text)
    expect(texts.filter((t) => t === 'Getting ready to search for my part.')).toHaveLength(1)
    expect(texts).toContain('Your idea needs 4 main parts. Writing them down.')
    expect(team.agents.scout.thought).toBe('That did not work. Trying another way.')
  })

  it('says "getting started" only once per agent, so real actions are not pushed out', () => {
    const team = teamFromEvents([
      ev('node_started', { node: 'research_lead' }),
      ev('agent_action', { agent: 'research_lead', tool: 'ask_component_scouts', count: 3, ok: true }),
      ev('node_finished', { node: 'research_lead' }),
      ev('node_started', { node: 'research_lead' }),
      ev('usage', { service: 'jev' }),
      ev('usage', { service: 'jev' }),
    ])
    expect(team.thoughts.map((t) => t.text)).toEqual([
      'Reading your brief to plan who does what.',
      'Sending 3 scouts, one for each part.',
      'Weighing every option: fit, risk, and whether a person should review it.',
    ])
  })

  it('keeps only the latest few thoughts', () => {
    const events = Array.from({ length: 10 }, (_, i) =>
      ev('agent_action', { agent: 'component_scout', tool: 'search_github', about: `q${i}`, ok: true }),
    )
    const team = teamFromEvents(events)
    expect(team.thoughts).toHaveLength(4)
    expect(team.thoughts.at(-1)?.text).toContain('q9')
  })
})

describe('the stream below the robots', () => {
  it('puts thoughts and messages together in the order they happened', () => {
    const team = teamFromEvents([
      ev('node_started', { node: 'research_lead' }),
      ev('team_message', { sender: 'research_lead', recipient: 'component_scout', message: 'Search CAP-1' }),
      ev('agent_action', { agent: 'component_scout', tool: 'search_github', about: 'pdf parsing', ok: true }),
    ])
    expect(team.stream.map((line) => line.kind)).toEqual(['thought', 'message', 'thought'])
    expect(team.stream[1]).toMatchObject({ kind: 'message', from: 'lead', to: 'scout', text: 'Search CAP-1' })
  })
})

describe('teamFromEvents: designing the options', () => {
  it('huddles while drafting: three agents hand their work to the lead, who drafts', () => {
    const team = teamFromEvents([ev('options_started'), ev('node_started', { node: 'draft_options' })])
    expect(team.designing).toBe(true)
    expect(team.agents.lead).toMatchObject({ status: 'working', doing: 'Drafting architecture options' })
    expect(team.messages.map((m) => [m.from, m.to])).toEqual([['analyst', 'lead'], ['scout', 'lead'], ['decider', 'lead']])
    expect(new Set(team.messages.map((m) => m.id)).size).toBe(3) // each hand-over is its own cable
  })

  it('hands the drafts to the reviewer and the judge, and says the review result', () => {
    const team = teamFromEvents([
      ev('node_started', { node: 'draft_options' }),
      ev('node_finished', { node: 'draft_options' }),
      ev('node_started', { node: 'review_options' }),
      ev('activity', { message: 'Options review: 2 passed, 1 did not' }),
    ])
    expect(team.agents.lead.status).toBe('done')
    expect(team.agents.reviewer.status).toBe('working')
    expect(team.agents.judge.status).toBe('working')
    expect(team.messages.at(-1)).toMatchObject({ from: 'lead', to: 'reviewer' })
    expect(team.agents.reviewer.thought).toBe('Review done: 2 passed, 1 did not')
  })

  it('stops huddling when the options wait for the person, or the run stops', () => {
    const drafting = [ev('node_started', { node: 'draft_options' }), ev('node_finished', { node: 'draft_options' }), ev('node_started', { node: 'review_options' }), ev('node_finished', { node: 'review_options' })]
    expect(teamFromEvents([...drafting, ev('node_waiting', { node: 'select_or_revise' })]).designing).toBe(false)
    expect(teamFromEvents([ev('node_started', { node: 'draft_options' }), ev('run_error', { message: 'x' })]).designing).toBe(false)
    expect(teamFromEvents(drafting).live).toBe(false)
  })
})
