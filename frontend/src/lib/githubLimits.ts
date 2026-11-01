/**
 * Small pure helpers for the GitHub limit bar, kept apart so they can be tested.
 */

export type MeterTone = 'ok' | 'low' | 'empty'

/** "7:05" for 425 seconds; "1:02:03" once it passes an hour. Never negative. */
export function formatCountdown(totalSeconds: number): string {
  const seconds = Math.max(0, Math.floor(totalSeconds))
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const rest = String(seconds % 60).padStart(2, '0')
  if (hours > 0) return `${hours}:${String(minutes).padStart(2, '0')}:${rest}`
  return `${minutes}:${rest}`
}

/** How alarming a meter is: empty at zero, low at 20% or less, otherwise ok. */
export function meterTone(remaining: number, limit: number): MeterTone {
  if (remaining <= 0) return 'empty'
  if (limit > 0 && remaining / limit <= 0.2) return 'low'
  return 'ok'
}

/** How many calls have been used: GitHub reports what is left, the bar shows what is spent. */
export function usedCount(remaining: number, limit: number): number {
  return Math.min(limit, Math.max(0, limit - remaining))
}

/** Share of the allowance already used, 0 to 100. Zero is untouched, 100 is used up. */
export function usedPercent(remaining: number, limit: number): number {
  if (limit <= 0) return 0
  return Math.round((usedCount(remaining, limit) / limit) * 100)
}

/**
 * Seconds left until the allowance refills, counted down from the moment the
 * answer arrived. Measured in the browser from "seconds until reset" (not from
 * a clock time), so a wrong clock on this computer cannot make it drift.
 */
export function secondsUntilReset(secondsAtReceipt: number, receivedAtMs: number, nowMs: number): number {
  return Math.max(0, secondsAtReceipt - (nowMs - receivedAtMs) / 1000)
}
