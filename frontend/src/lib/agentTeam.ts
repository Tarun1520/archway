/**
 * The research team as the agents corner draws it: who is working, what each
 * one is doing, and the messages they pass to each other.
 *
 * It is worked out from the run's real event stream only (the same events the
 * activity feed reads), so a robot moves only when its agent really does.
 */
import type { StreamEvent } from './api/types'
import { STARTING_THOUGHT, thoughtForAction } from './agentThoughts'

export type AgentId = 'lead' | 'analyst' | 'scout' | 'judge' | 'projects' | 'reviewer' | 'decider'
export type AgentStatus = 'idle' | 'working' | 'done'

export interface AgentState {
  id: AgentId
  /** Short name under the robot. */
  label: string
  /** One line saying what the agent is for. */
  role: string
  status: AgentStatus
  /** What it is doing right now, in plain words; null when idle. */
  doing: string | null
  /** How many copies are working at once (scouts run one per capability). */
  copies: number
  /** Its latest thought, in simple first-person words; null before it starts. */
  thought: string | null
}

/** One line of the stream below the robots: a thought, or a message between agents, in the order they happened. */
export type StreamLine =
  | { id: string; kind: 'thought'; agent: AgentId; text: string }
  | { id: string; kind: 'message'; from: AgentId | 'team'; to: AgentId | 'team'; text: string }

/** One thought, as the "thinking" list below the robots shows it. */
export interface ThoughtLine {
  id: string
  agent: AgentId
  text: string
}

export interface TeamMessageLine {
  id: string
  from: AgentId | 'team'
  to: AgentId | 'team'
  text: string
}

export interface TeamPicture {
  agents: Record<AgentId, AgentState>
  /** The latest messages, newest last. */
  messages: TeamMessageLine[]
  /** The latest thoughts across the team, newest last. */
  thoughts: ThoughtLine[]
  /** Thoughts and messages together, in the order they happened, newest last. */
  stream: StreamLine[]
  /** True while any agent is working. */
  live: boolean
  /** True once the team has done anything in this run. */
  started: boolean
  /** True while the architecture options are being drafted and reviewed: the team huddles round the lead. */
  designing: boolean
}

/** The team in the order the corner draws it: the lead in the middle of everything. */
export const AGENTS: { id: AgentId; label: string; role: string }[] = [
  { id: 'lead', label: 'Lead', role: 'Decides who works next' },
  { id: 'analyst', label: 'Analyst', role: 'Splits the idea into capabilities' },
  { id: 'scout', label: 'Scouts', role: 'Search and verify open-source parts' },
  { id: 'judge', label: 'Judge', role: 'Checks each find, blind to the pitch' },
  { id: 'projects', label: 'Projects', role: 'Finds similar whole projects' },
  { id: 'reviewer', label: 'Reviewer', role: 'Looks for gaps' },
  { id: 'decider', label: 'Laya', role: 'Decides fit, risk and review' },
]

/** Backend agent and node names, mapped to the robots. */
const BY_BACKEND_NAME: Record<string, AgentId> = {
  research_lead: 'lead',
  capability_analyst: 'analyst',
  component_scout: 'scout',
  relevance_judge: 'judge',
  project_scout: 'projects',
  reviewer: 'reviewer',
  evaluate_candidates: 'decider',
}

/**
 * The options stage (Phase 5), as the robots act it out. Drafting is ONE model call made by the lead, from three
 * inputs the others produced: the capabilities and must-haves (analyst), the parts that passed the rules (scouts)
 * and the decisions about each part (Laya). So when drafting starts, those three hand their work to the lead over
 * a cable, and the lead drafts. The review is the reviewer's (against the brief) and the judge's (against the
 * evidence). Every move follows a real event: drafting starting, review starting, the review's result.
 */
const OPTION_HANDOVERS: { from: AgentId; text: string }[] = [
  { from: 'analyst', text: 'The capabilities and your must-haves' },
  { from: 'scout', text: 'The parts that passed the rules' },
  { from: 'decider', text: 'What I decided about each part' },
]

/** What a tool call means, in words anyone can follow. */
const DOING: Record<string, string> = {
  search_github: 'Searching GitHub',
  inspect_repository: 'Reading a repository',
  lookup_pypi: 'Checking a Python package',
  lookup_npm: 'Checking an npm package',
  search_npm: 'Searching npm',
  read_web_page: 'Reading documentation',
  search_discussions: 'Reading developer forums',
  search_web: 'Searching the web',
  find_curated_lists: 'Reading curated lists',
  record_capabilities: 'Listing capabilities',
  submit_components: 'Reporting finds',
  submit_projects: 'Reporting projects',
  submit_review: 'Writing the review',
  submit_fit: 'Scoring relevance',
  ask_capability_analyst: 'Briefing the analyst',
  ask_component_scouts: 'Sending out scouts',
  ask_project_scout: 'Briefing the project scout',
  ask_reviewer: 'Asking for a review',
  finish_research: 'Wrapping up',
}

const START_DOING: Record<AgentId, string> = {
  lead: 'Deciding the next step',
  analyst: 'Reading the brief',
  scout: 'Starting a search',
  judge: 'Scoring relevance',
  projects: 'Looking for similar projects',
  reviewer: 'Checking coverage',
  decider: 'Weighing every option',
}

function agentOf(name: string | undefined): AgentId | null {
  return name ? (BY_BACKEND_NAME[name] ?? null) : null
}

function fresh(): Record<AgentId, AgentState> {
  return Object.fromEntries(
    AGENTS.map((a) => [a.id, { ...a, status: 'idle' as AgentStatus, doing: null, copies: 0, thought: null }]),
  ) as Record<AgentId, AgentState>
}

const MAX_MESSAGES = 6
const MAX_THOUGHTS = 4
/** Every thought and message of a run is kept (a research run is a few hundred at most); this is only a safety limit. */
const MAX_STREAM = 500

export function teamFromEvents(events: StreamEvent[]): TeamPicture {
  const agents = fresh()
  const messages: TeamMessageLine[] = []
  const thoughts: ThoughtLine[] = []
  const stream: StreamLine[] = []
  let started = false
  let designing = false
  const toStream = (line: StreamLine) => {
    stream.push(line)
    if (stream.length > MAX_STREAM) stream.shift()
  }

  const think = (eventId: string, id: AgentId, text: string) => {
    // A thought the agent already has (many scouts starting at once, the
    // decider called again and again) is not repeated.
    if (agents[id].thought === text) return
    agents[id].thought = text
    thoughts.push({ id: eventId, agent: id, text })
    if (thoughts.length > MAX_THOUGHTS) thoughts.shift()
    toStream({ id: eventId, kind: 'thought', agent: id, text })
  }

  const work = (id: AgentId, doing: string) => {
    const agent = agents[id]
    agent.status = 'working'
    agent.doing = doing
    started = true
  }
  const rest = (id: AgentId) => {
    const agent = agents[id]
    agent.status = 'done'
    agent.doing = null
  }

  const say = (eventId: string, from: AgentId, to: AgentId, text: string) => {
    messages.push({ id: eventId, from, to, text })
    toStream({ id: eventId, kind: 'message', from, to, text })
    if (messages.length > MAX_MESSAGES) messages.shift()
  }

  for (const event of events) {
    // The options steps first: they are acted out by several robots at once.
    if (event.name === 'node_started' && event.data.node === 'draft_options') {
      designing = true
      started = true
      for (const handover of OPTION_HANDOVERS) {
        work(handover.from, 'Handing over to the lead')
        say(`${event.id}:${handover.from}`, handover.from, 'lead', handover.text)
        rest(handover.from)
      }
      work('lead', 'Drafting architecture options')
      think(event.id, 'lead', 'Sketching the ways to build it from the shortlist, and what each one costs.')
      continue
    }
    if (event.name === 'node_started' && event.data.node === 'review_options') {
      designing = true
      rest('lead')
      say(`${event.id}:review`, 'lead', 'reviewer', 'Here are the drafts: check them')
      work('reviewer', 'Checking options against your brief')
      work('judge', 'Checking claims against the evidence')
      think(event.id, 'reviewer', 'Does each option keep to your brief, and reuse only parts the rules allow?')
      continue
    }
    if (event.name === 'node_finished' && (event.data.node === 'draft_options' || event.data.node === 'review_options')) {
      if (event.data.node === 'draft_options') rest('lead')
      else {
        rest('reviewer')
        rest('judge')
      }
      continue
    }
    if (event.name === 'activity' && designing && (event.data.message ?? '').startsWith('Options review:')) {
      think(event.id, 'reviewer', (event.data.message ?? '').replace('Options review:', 'Review done:'))
      continue
    }
    if ((event.name === 'node_waiting' && (event.data.node === 'select_or_revise' || event.data.node === 'approve_version')) || event.name === 'workflow_finished' || event.name === 'run_error') {
      designing = false
    }

    const id = agentOf(event.data.node) ?? agentOf(event.data.agent)
    switch (event.name) {
      case 'node_started':
        if (id) {
          agents[id].copies += 1
          work(id, START_DOING[id])
          // Only the first start says "getting started": the lead, for one,
          // starts a new turn every time a specialist reports back.
          if (agents[id].thought === null) think(event.id, id, STARTING_THOUGHT[id])
        }
        break
      case 'node_finished':
        if (id) {
          agents[id].copies = Math.max(0, agents[id].copies - 1)
          if (agents[id].copies === 0) rest(id)
          // The judge works inside each scout's step: when the last scout is done, so is the judge.
          if (id === 'scout' && agents.scout.copies === 0 && agents.judge.status === 'working') rest('judge')
        }
        break
      case 'agent_action':
        if (id) {
          work(id, DOING[event.data.tool ?? ''] ?? 'Working')
          think(event.id, id, thoughtForAction(event.data.tool ?? '', event.data.about ?? null, event.data.count ?? null, event.data.ok !== false))
        }
        break
      case 'usage':
        if (event.data.service === 'jev') {
          work('decider', 'Deciding fit, risk and review')
          think(event.id, 'decider', STARTING_THOUGHT.decider)
        }
        break
      case 'team_message': {
        const from = agentOf(event.data.sender) ?? 'team'
        const to = agentOf(event.data.recipient) ?? 'team'
        messages.push({ id: event.id, from, to, text: event.data.message ?? '' })
        toStream({ id: event.id, kind: 'message', from, to, text: event.data.message ?? '' })
        if (messages.length > MAX_MESSAGES) messages.shift()
        started = true
        break
      }
      case 'run_error':
        for (const agent of Object.values(agents)) {
          if (agent.status === 'working') {
            agent.status = 'idle'
            agent.doing = null
            agent.copies = 0
          }
        }
        break
      case 'workflow_finished':
        for (const agent of Object.values(agents)) if (agent.status === 'working') rest(agent.id)
        break
      default:
        break
    }
  }

  const live = Object.values(agents).some((agent) => agent.status === 'working')
  return { agents, messages, thoughts, stream, live, started, designing }
}

/** A message, shortened for a speech bubble. */
export function bubbleText(text: string, max = 90): string {
  const clean = text.replace(/\s+/g, ' ').trim()
  return clean.length <= max ? clean : `${clean.slice(0, max - 1).trimEnd()}…`
}
