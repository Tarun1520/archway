import { describe, expect, it } from 'vitest'
import type { ResearchSnapshot } from './api/types'
import { sourceRows } from './sources'

const base = { components: [], capabilities: [], projects: [], messages: [], repos: [], evidence: [], notes: [], eligibility: [], receipts: [], review: null, finished: true, mode: 'live' } as unknown as ResearchSnapshot
const part = (kind: string) => ({ facts: { kind } }) as never

describe('sourceRows', () => {
  it('shows only the sources the run really used, grouped, with what was done in the tooltip', () => {
    const rows = sourceRows({ ...base, sources: [
      { source: 'github', lookups: 4, results: 20 },
      { source: 'pypi', lookups: 1, results: 1 },
      { source: 'hacker_news', lookups: 2, results: 6 },
    ] })
    expect(rows.map((r) => r.badges.map((b) => b.name))).toEqual([['GitHub', 'PyPI'], ['Hacker News']])
    expect(rows[0].badges[0].detail).toBe('20 results from 4 lookups')
    expect(rows[0].badges[1].detail).toBe('1 result from 1 lookup')
  })

  it('shows nothing for sources that were not used', () => {
    expect(sourceRows({ ...base, sources: [{ source: 'brave', lookups: 1, results: 3 }] }).map((r) => r.badges[0].name)).toEqual(['Brave'])
  })

  it('for older runs with no record, claims only the registries the parts really came from', () => {
    const rows = sourceRows({ ...base, components: [part('github'), part('github'), part('npm')] })
    expect(rows).toHaveLength(1)
    expect(rows[0].badges.map((b) => `${b.name}: ${b.detail}`)).toEqual(['GitHub: 2 parts found here', 'npm: 1 part found here'])
  })

  it('is empty when nothing is known', () => {
    expect(sourceRows(base)).toEqual([])
  })
})
