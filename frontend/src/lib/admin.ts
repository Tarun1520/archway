/**
 * Small helpers for the admin dashboard.
 *
 *   formatTokens(1_250_000)   "1.25M"
 *   quotaShare(row)           how full the quota is (0 to 1, can pass 1), or null when there is no limit
 *   sinceText(time)           "just now", "12s ago", "5 min ago", "3 h ago", "2 d ago"
 */
import type { UserUsage } from './api/types'

export function formatTokens(value: number): string {
  if (value >= 1_000_000) return `${Number((value / 1_000_000).toFixed(2))}M`
  if (value >= 1_000) return `${Number((value / 1_000).toFixed(1))}k`
  return String(value)
}

export function quotaShare(row: UserUsage): number | null {
  const quota = row.user.monthly_token_quota
  return quota ? row.tokens / quota : null
}

export function sinceText(time: number, now: number = Date.now()): string {
  const seconds = Math.max(0, Math.round((now - time) / 1000))
  if (seconds < 5) return 'just now'
  if (seconds < 60) return `${seconds}s ago`
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.round(minutes / 60)
  if (hours < 48) return `${hours} h ago`
  return `${Math.round(hours / 24)} d ago`
}
