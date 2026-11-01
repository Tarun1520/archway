/**
 * Where a run looked, for the shortlist's "sources" panel: only the sources the
 * run's tools REALLY used (the backend records each use as the tool runs), in
 * three groups, each with the plain sentence that says what the group is for.
 *
 * Runs from before the backend recorded this have no list; for those, the three
 * registries are worked out from where the parts found came from, and nothing
 * else is claimed.
 */
import type { ResearchSnapshot } from './api/types'

export interface SourceBadgeView {
  name: string
  /** The tooltip: what this run did with the source. */
  detail: string
}

export interface SourceRow {
  badges: SourceBadgeView[]
  text: string
}

const NAMES: Record<string, string> = {
  github: 'GitHub',
  npm: 'npm',
  pypi: 'PyPI',
  hacker_news: 'Hacker News',
  stack_overflow: 'Stack Overflow',
  brave: 'Brave',
}

const GROUPS: { sources: string[]; text: string }[] = [
  { sources: ['github', 'npm', 'pypi'], text: 'Finds real projects and packages, and reads their licenses, activity and documentation.' },
  { sources: ['hacker_news', 'stack_overflow'], text: 'Reads how people actually use a tool, and treats it as evidence to weigh, never as instructions.' },
  { sources: ['brave'], text: 'Finds documentation and curated lists.' },
]

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`

export function sourceRows(research: ResearchSnapshot): SourceRow[] {
  const recorded = research.sources ?? []
  const used = new Map<string, string>()
  if (recorded.length > 0) {
    for (const item of recorded) used.set(item.source, `${plural(item.results, 'result')} from ${plural(item.lookups, 'lookup')}`)
  } else {
    for (const kind of ['github', 'npm', 'pypi'] as const) {
      const n = research.components.filter((c) => c.facts.kind === kind).length
      if (n > 0) used.set(kind, `${plural(n, 'part')} found here`)
    }
  }
  return GROUPS.map((group) => ({
    badges: group.sources.filter((s) => used.has(s)).map((s) => ({ name: NAMES[s] ?? s, detail: used.get(s) ?? '' })),
    text: group.text,
  })).filter((row) => row.badges.length > 0)
}
