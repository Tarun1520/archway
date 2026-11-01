/**
 * What an agent is "thinking", in simple first-person words anyone can follow.
 *
 * Built only from what the agent really did (its tool calls and when it
 * started), so a thought is never invented. `about` is the subject the backend
 * read from the call's arguments (search words, a repository name); it is shown
 * as plain text inside quotes and never interpreted.
 */
import type { AgentId } from './agentTeam'

/** A sentence for one tool call. `about` and `count` may be missing. */
export function thoughtForAction(tool: string, about: string | null, count: number | null, ok: boolean): string {
  if (!ok) return 'That did not work. Trying another way.'
  const quoted = about ? `“${about}”` : null
  switch (tool) {
    case 'search_github':
      return quoted ? `Let me look on GitHub for ${quoted}.` : 'Let me look on GitHub.'
    case 'inspect_repository':
      return quoted ? `Opening ${quoted} to see what it does and how it is licensed.` : 'Opening a project to see what it does.'
    case 'lookup_pypi':
    case 'lookup_npm':
      return quoted ? `Is ${quoted} a real, looked-after package? Checking.` : 'Checking a package is real and looked after.'
    case 'search_npm':
      return quoted ? `Searching JavaScript packages for ${quoted}.` : 'Searching JavaScript packages.'
    case 'read_web_page':
      return quoted ? `Reading the documentation at ${quoted}.` : 'Reading some documentation.'
    case 'search_discussions':
      return quoted ? `What do developers say about ${quoted}? Reading their forums.` : 'Reading what developers say.'
    case 'search_web':
      return quoted ? `Searching the web for ${quoted}.` : 'Searching the web.'
    case 'find_curated_lists':
      return quoted ? `Are there trusted lists of tools for ${quoted}?` : 'Looking for trusted lists of tools.'
    case 'record_capabilities':
      return count ? `Your idea needs ${count} main parts. Writing them down.` : 'Writing down the parts your idea needs.'
    case 'submit_components':
      return count ? `Found ${count} ${plural(count, 'part')} worth keeping. Handing them in.` : 'Handing in what I found.'
    case 'submit_projects':
      return count ? `Found ${count} similar ${plural(count, 'project')}.` : 'Handing in similar projects.'
    case 'submit_review':
      return 'Checked whether anything important was missed.'
    case 'submit_fit':
      return count ? `Scored ${count} ${plural(count, 'find')}: does each one really fit your idea?` : 'Scoring how well each find fits.'
    case 'ask_capability_analyst':
      return 'First: what parts does this idea need? Asking the analyst.'
    case 'ask_component_scouts':
      return count ? `Sending ${count} ${plural(count, 'scout')}, one for each part.` : 'Sending out the scouts.'
    case 'ask_project_scout':
      return 'Are there finished apps like this? Asking the project scout.'
    case 'ask_reviewer':
      return 'Before finishing: did we miss anything? Asking the reviewer.'
    case 'finish_research':
      return 'That covers it. Wrapping up the research.'
    default:
      return 'Working on it.'
  }
}

/** The first thought when an agent starts its turn. */
export const STARTING_THOUGHT: Record<AgentId, string> = {
  lead: 'Reading your brief to plan who does what.',
  analyst: 'Reading your brief to find the parts it really needs.',
  scout: 'Getting ready to search for my part.',
  judge: 'Checking each find against your idea, not its sales pitch.',
  projects: 'Looking for finished apps like yours.',
  reviewer: 'Looking for anything the team missed.',
  decider: 'Weighing every option: fit, risk, and whether a person should review it.',
}

function plural(count: number, word: string): string {
  return count === 1 ? word : `${word}s`
}
