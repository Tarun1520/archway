import type { GithubLimitMeter } from '../../lib/api/types'
import type { GithubLimitsState } from '../../hooks/useGithubLimits'
import { formatCountdown, meterTone, secondsUntilReset, usedCount, usedPercent, type MeterTone } from '../../lib/githubLimits'

const FILL: Record<MeterTone, string> = {
  ok: 'bg-cobalt',
  low: 'bg-oak',
  empty: 'bg-oak',
}

interface MeterProps {
  label: string
  /** What this allowance pays for, shown on hover. */
  hint: string
  meter: GithubLimitMeter
  receivedAt: number
  now: number
}

/** One allowance: a label, a bar of what is left, the numbers, and a countdown once it is used up. */
function Meter({ label, hint, meter, receivedAt, now }: MeterProps) {
  const tone = meterTone(meter.remaining, meter.limit)
  const used = usedCount(meter.remaining, meter.limit)
  const percent = usedPercent(meter.remaining, meter.limit)
  const resetIn = secondsUntilReset(meter.seconds_until_reset, receivedAt, now)
  // Once the countdown has run out the allowance has refilled; the hook is
  // already fetching the new numbers, so show "refilling" rather than 0:00.
  const refilling = tone === 'empty' && resetIn <= 0

  return (
    <span className="inline-flex items-center gap-8 whitespace-nowrap" title={`${hint} Refills in ${formatCountdown(resetIn)}.`}>
      <span className="text-ash">{label}</span>
      <span
        role="progressbar"
        aria-label={`${label}: ${used} of ${meter.limit} used`}
        aria-valuemin={0}
        aria-valuemax={meter.limit}
        aria-valuenow={used}
        className="relative inline-block h-6 w-56 overflow-hidden rounded-pill bg-mist/15"
      >
        <span
          className={`absolute inset-y-0 left-0 rounded-pill transition-[width] duration-500 ${FILL[tone]}`}
          style={{ width: `${percent}%` }}
        />
      </span>
      <span className="text-ivory">
        {used}/{meter.limit} used
      </span>
      {/*
        The bar fills as calls are USED (40/60 used reads as two thirds full;
        60/60 is used up). The timer shows whenever any of it has been used,
        because from then on a refill is coming. Untouched, there is nothing to
        count down to (GitHub's window starts at the first use), so it says
        "unused".
      */}
      {tone === 'empty' ? (
        <span className="text-oak" aria-live="polite">
          {refilling ? 'refilling…' : `empty · resets in ${formatCountdown(resetIn)}`}
        </span>
      ) : used > 0 ? (
        <span className="text-ash">refills in {formatCountdown(resetIn)}</span>
      ) : (
        <span className="text-ash">unused</span>
      )}
    </span>
  )
}

/**
 * GitHub's real allowance, from GitHub itself: repository reads (per hour) and
 * searches (per minute). When one is used up, a countdown shows when it
 * refills. Hidden in fixture mode, where no real limit applies.
 */
export function GithubLimitBar({ state }: { state: GithubLimitsState }) {
  const { limits, failed, receivedAt, now } = state
  // Say what is happening instead of vanishing, so a missing bar is never a mystery.
  if (!limits) {
    return <span className="font-mono text-caption text-ash">{failed ? 'GitHub limits unavailable' : 'GitHub limits: checking…'}</span>
  }
  if (!limits.available || (!limits.core && !limits.search)) return null // fixture mode: no real limit

  return (
    <div className="flex flex-wrap items-center gap-x-16 gap-y-4 font-mono text-caption" aria-label="GitHub allowance">
      {limits.core && (
        <Meter
          label="GitHub reads"
          hint="Repository details, READMEs and licenses, per hour."
          meter={limits.core}
          receivedAt={receivedAt}
          now={now}
        />
      )}
      {limits.search && (
        <Meter
          label="searches"
          hint="Repository searches, per minute."
          meter={limits.search}
          receivedAt={receivedAt}
          now={now}
        />
      )}
      {limits.authenticated && (
        <span className="text-ash" title="A GitHub token is in use, so the larger allowance applies.">
          token
        </span>
      )}
      {!limits.authenticated && (
        <span className="text-ash" title="Without a token GitHub allows 60 reads an hour. Add GITHUB_TOKEN to backend/.env for 5,000.">
          no token
        </span>
      )}
    </div>
  )
}
