import { describe, expect, it } from 'vitest'
import type { UserUsage } from './api/types'
import { formatTokens, quotaShare, sinceText } from './admin'

const row = (tokens: number, quota: number | null) => ({ tokens, user: { monthly_token_quota: quota } }) as unknown as UserUsage

describe('admin helpers', () => {
  it('writes token counts short', () => {
    expect([formatTokens(0), formatTokens(950), formatTokens(12_400), formatTokens(2_000_000), formatTokens(1_250_000)]).toEqual(['0', '950', '12.4k', '2M', '1.25M'])
  })

  it('says how full a quota is, and nothing when there is no limit', () => {
    expect(quotaShare(row(500, 1000))).toBe(0.5)
    expect(quotaShare(row(1500, 1000))).toBe(1.5)
    expect(quotaShare(row(500, null))).toBeNull()
  })

  it('says how long ago, in plain words', () => {
    const now = 1_000_000_000
    expect(sinceText(now - 2_000, now)).toBe('just now')
    expect(sinceText(now - 30_000, now)).toBe('30s ago')
    expect(sinceText(now - 5 * 60_000, now)).toBe('5 min ago')
    expect(sinceText(now - 3 * 3_600_000, now)).toBe('3 h ago')
    expect(sinceText(now - 3 * 86_400_000, now)).toBe('3 d ago')
  })
})
