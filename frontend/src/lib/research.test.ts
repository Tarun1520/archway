import { describe, expect, it } from 'vitest'
import { absenceWord, agentLabel, formatWhen, licenseView, safeHref, shortHash, sourceLabel } from './research'

describe('licenseView', () => {
  it('names the four license states apart', () => {
    expect(licenseView({ kind: 'github', license: 'MIT', license_status: 'detected' })).toEqual({ kind: 'detected', label: 'MIT' })
    expect(licenseView({ kind: 'github', license: 'NOASSERTION', license_status: 'unrecognised' }).kind).toBe('unrecognised')
    expect(licenseView({ kind: 'github', license: null, license_status: 'none_detected' }).label).toBe('No license detected')
    expect(licenseView({ kind: 'pypi', license: null, license_status: 'none_detected' }).label).toBe('No license declared')
    expect(licenseView({ kind: 'npm', license: null, license_status: 'not_retrieved' }).label).toBe('License not retrieved')
  })

  it('names the agents', () => {
    expect(agentLabel('component_scout')).toBe('Component scout')
    expect(agentLabel('team')).toBe('Team')
  })
})

describe('absence', () => {
  it('says "not retrieved" only for fields that were tried and failed', () => {
    expect(absenceWord('readme_excerpt', ['readme_excerpt'])).toBe('not retrieved')
    expect(absenceWord('language', [])).toBe('not reported')
  })
})

describe('presentation helpers', () => {
  it('formats dates in UTC with the zone shown', () => {
    expect(formatWhen('2026-10-14T17:22:09Z')).toBe('14 Oct 2026, 17:22 UTC')
    expect(formatWhen('not a date')).toBe('not a date')
  })

  it('links only https addresses', () => {
    expect(safeHref('https://github.com/a/b')).toBe('https://github.com/a/b')
    expect(safeHref('http://localhost/x')).toBeNull()
    expect(safeHref('javascript:alert(1)')).toBeNull()
  })

  it('shortens hashes and labels sources', () => {
    expect(shortHash('abcdef0123456789abcdef')).toBe('abcdef012345')
    expect(shortHash(null)).toBeNull()
    expect(sourceLabel('readme')).toBe('README')
  })
})


describe('relevance helpers', () => {
  const make = (fit: number | null, stars: number | null = null) =>
    ({ id: `c${fit}${stars}`, fit, facts: { stars } }) as unknown as import('./api/types').ComponentCandidate

  it('counts reference-only components as not building blocks, and unassessed ones as building blocks', async () => {
    const { isBuildingBlock } = await import('./research')
    expect(isBuildingBlock(make(1))).toBe(false)
    expect(isBuildingBlock(make(2))).toBe(true)
    expect(isBuildingBlock(make(3))).toBe(true)
    expect(isBuildingBlock(make(null))).toBe(true)
  })

  it('sorts by judged fit first, then by adoption', async () => {
    const { byRelevance } = await import('./research')
    const sorted = [make(2, 900), make(3, 5), make(3, 50)].sort(byRelevance)
    expect(sorted.map((c) => [c.fit, c.facts.stars])).toEqual([[3, 50], [3, 5], [2, 900]])
  })
})


describe('adoption', () => {
  it('treats known small numbers as low adoption, unknown as not low', async () => {
    const { isLowAdoption, shortCount } = await import('./research')
    const f = (kind: 'github' | 'npm', stars: number | null, downloads: number | null) =>
      ({ kind, stars, downloads_last_month: downloads }) as unknown as import('./api/types').SourceFacts
    expect(isLowAdoption(f('github', 3, null))).toBe(true)
    expect(isLowAdoption(f('github', null, null))).toBe(false)
    expect(isLowAdoption(f('npm', null, 120))).toBe(true)
    expect(isLowAdoption(f('npm', null, 2_355_152))).toBe(false)
    expect(shortCount(2_355_152)).toBe('2.4M')
    expect(shortCount(95_391)).toBe('95k')
  })
})
