/**
 * Turning a run's saved events into what the screen shows.
 *
 * The backend saves one numbered event for each real thing the workflow does
 * (backend/app/workflow/service.py). This file reads that list and works out:
 *
 *   - the status of each step, for the workflow view
 *   - the lines of the activity feed
 *
 * It is a "pure" function: the same events always give the same result, and
 * it touches nothing else. That makes it easy to test, and it means the
 * workflow view can only ever show what an event actually reported.
 */
import type { StreamEvent, WorkflowNode } from './api/types'
import { agentLabel } from './research'

export type NodeStatus = 'idle' | 'active' | 'waiting' | 'done'

/**
 * The steps of the workflow, in the order they are drawn. The first three are
 * the brief stage; the rest are the AGENTS of the research team, which the
 * research lead calls in whatever order it decides.
 */
export const WORKFLOW_NODES: { id: WorkflowNode; label: string }[] = [
  { id: 'intake', label: 'Read idea' },
  { id: 'clarify', label: 'Ask questions' },
  { id: 'confirm_brief', label: 'Confirm brief' },
  { id: 'research_lead', label: 'Research lead' },
  { id: 'capability_analyst', label: 'Capability analyst' },
  { id: 'component_scout', label: 'Component scouts' },
  { id: 'project_scout', label: 'Project scout' },
  { id: 'reviewer', label: 'Reviewer' },
  { id: 'evaluate_candidates', label: 'Decisions' },
  { id: 'draft_options', label: 'Draft options' },
  { id: 'review_options', label: 'Review options' },
  { id: 'select_or_revise', label: 'Choose an option' },
  { id: 'approve_version', label: 'Approve a version' },
  { id: 'build_roadmap', label: 'Plan the build' },
  { id: 'generate_prompts', label: 'Write the prompts' },
  { id: 'check_prompts', label: 'Check the prompts' },
  { id: 'export', label: 'Export the plan' },
]

export interface FeedLine {
  id: string
  text: string
  /** True for a problem, so the feed can mark it with an icon and a label. */
  isError: boolean
}

export interface Progress {
  nodes: Record<WorkflowNode, NodeStatus>
  feed: FeedLine[]
  /** The newest error, cleared when the run is started again. */
  error: string | null
  finished: boolean
  /** How many research events have arrived. When it changes, the research data is worth reloading. */
  researchVersion: number
  /** How many options events have arrived. When it changes, the saved options are worth reloading. */
  optionsVersion: number
  /** How many plan events have arrived. When it changes, the saved plan is worth reloading. */
  planVersion: number
}

const NODE_NAMES: Record<string, string> = Object.fromEntries(WORKFLOW_NODES.map((node) => [node.id, node.label]))

function isWorkflowNode(value: string | undefined): value is WorkflowNode {
  return WORKFLOW_NODES.some((node) => node.id === value)
}

/** Events that mean the saved research changed, so the Research tab should reload. */
const RESEARCH_EVENTS = new Set(['capabilities_recorded', 'components_proposed', 'team_message', 'eligibility_decided'])

/** Events that mean the saved options changed, so the Options step should reload. */
const OPTIONS_EVENTS = new Set(['options_updated', 'option_approved'])

/** Events that mean the saved plan changed, so the Plan step should reload. */
const PLAN_EVENTS = new Set(['plan_started', 'plan_updated'])

/** Agents that run several copies at once; their "finished" line would repeat. */
const PARALLEL_AGENTS = new Set(['component_scout'])

export function emptyProgress(): Progress {
  const nodes = Object.fromEntries(WORKFLOW_NODES.map((node) => [node.id, 'idle'])) as Record<WorkflowNode, NodeStatus>
  return { nodes, feed: [], error: null, finished: false, researchVersion: 0, optionsVersion: 0, planVersion: 0 }
}

/** Reads the events in order and returns the picture they add up to. */
export function progressFromEvents(events: StreamEvent[]): Progress {
  const progress = emptyProgress()
  const say = (event: StreamEvent, text: string, isError = false) =>
    progress.feed.push({ id: event.id, text, isError })
  // Some steps run several times at once (one per repository). A step counts
  // as working until every copy of it has finished.
  const running: Partial<Record<WorkflowNode, number>> = {}

  for (const event of events) {
    const node = event.data.node
    const label = node ? (NODE_NAMES[node] ?? node) : ''

    switch (event.name) {
      case 'run_started':
        say(event, 'Run started')
        break
      case 'run_resumed':
        progress.error = null
        say(event, 'Run continued')
        break
      case 'node_started':
        if (isWorkflowNode(node)) {
          running[node] = (running[node] ?? 0) + 1
          progress.nodes[node] = 'active'
        }
        break
      case 'node_waiting':
        if (isWorkflowNode(node)) progress.nodes[node] = 'waiting'
        say(event, `${label}: waiting for you`)
        break
      case 'node_finished':
        if (isWorkflowNode(node)) {
          running[node] = Math.max(0, (running[node] ?? 0) - 1)
          progress.nodes[node] = (running[node] ?? 0) > 0 ? 'active' : 'done'
        }
        // The research lead runs between every agent; its "finished" lines would
        // drown the feed, and parallel scouts would repeat theirs. The team
        // messages below say what happened instead.
        if (node && node !== 'research_lead' && !PARALLEL_AGENTS.has(node)) say(event, `${label}: finished`)
        break
      case 'activity':
        if (event.data.message) say(event, event.data.message)
        break
      case 'usage': {
        const what = event.data.service === 'github' ? 'GitHub request' : 'Model call'
        say(event, `${what} made (${event.data.mode ?? 'unknown mode'})`)
        break
      }
      case 'rate_limited':
        say(event, 'GitHub asked us to slow down (rate limit)')
        break
      case 'team_message':
        say(event, `${agentLabel(event.data.sender ?? '')} → ${agentLabel(event.data.recipient ?? '')}: ${event.data.message ?? ''}`)
        break
      case 'options_started':
        say(event, 'Architecture options requested')
        break
      case 'run_error':
        progress.error = event.data.message ?? 'The run stopped on an error.'
        // A step that was working is no longer working.
        for (const item of WORKFLOW_NODES) {
          if (progress.nodes[item.id] === 'active') progress.nodes[item.id] = 'idle'
          running[item.id] = 0
        }
        say(event, progress.error, true)
        break
      case 'workflow_finished':
        progress.finished = true
        if (event.data.message) say(event, event.data.message)
        break
      default:
        break
    }
    if (RESEARCH_EVENTS.has(event.name)) progress.researchVersion += 1
    if (OPTIONS_EVENTS.has(event.name)) progress.optionsVersion += 1
    if (PLAN_EVENTS.has(event.name)) progress.planVersion += 1
  }
  return progress
}
