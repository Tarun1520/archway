import { describe, expect, it } from 'vitest'
import { formatCountdown, meterTone, secondsUntilReset, usedCount, usedPercent } from './githubLimits'

describe('formatCountdown', () => {
  it('shows minutes and seconds', () => {
    expect(formatCountdown(425)).toBe('7:05')
    expect(formatCountdown(9)).toBe('0:09')
  })
  it('shows hours once past an hour, and never goes negative', () => {
    expect(formatCountdown(3723)).toBe('1:02:03')
    expect(formatCountdown(-5)).toBe('0:00')
  })
})

describe('meterTone', () => {
  it('is empty at zero, low at 20% or less, otherwise ok', () => {
    expect(meterTone(0, 60)).toBe('empty')
    expect(meterTone(12, 60)).toBe('low')
    expect(meterTone(13, 60)).toBe('ok')
  })
})

describe('usedCount and usedPercent', () => {
  it('turns "left" into "used", so a full allowance reads 0 used', () => {
    expect(usedCount(60, 60)).toBe(0)
    expect(usedCount(20, 60)).toBe(40)
    expect(usedCount(0, 60)).toBe(60)
  })
  it('is bounded between 0 and 100 percent', () => {
    expect(usedPercent(20, 60)).toBe(67)
    expect(usedPercent(70, 60)).toBe(0)
    expect(usedPercent(5, 0)).toBe(0)
  })
})

describe('secondsUntilReset', () => {
  it('counts down from the time the answer arrived', () => {
    expect(secondsUntilReset(100, 1_000, 31_000)).toBe(70)
    expect(secondsUntilReset(10, 0, 60_000)).toBe(0)
  })
})
