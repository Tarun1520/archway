import type { ModeReport } from '../../lib/api/types'

/** A filled dot inside a ring: "recorded". Drawn for FIXTURE. */
function FixtureIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
      <circle cx="7" cy="7" r="5.75" stroke="currentColor" strokeWidth="1.5" strokeDasharray="2.5 2.5" />
      <circle cx="7" cy="7" r="2" fill="currentColor" />
    </svg>
  )
}

/** A solid dot with a solid ring: "on air". Drawn for LIVE. */
function LiveIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
      <circle cx="7" cy="7" r="5.75" stroke="currentColor" strokeWidth="1.5" />
      <circle cx="7" cy="7" r="3" fill="currentColor" />
    </svg>
  )
}

/**
 * The LIVE / FIXTURE badge.
 *
 * It reads LIVE only when every service (Jev, the LLM, GitHub) is live. If any
 * one is answering from recorded data, it reads FIXTURE and names which ones,
 * so a demo can never be mistaken for a real run.
 *
 * The state is carried by the WORD and the icon shape (dashed ring or solid
 * ring), not by color, so it reads the same for everyone.
 */
export function ModeBadge({ modes }: { modes: ModeReport }) {
  const isLive = modes.badge === 'LIVE'
  return (
    <span
      role="status"
      aria-label={`Service mode: ${modes.label}`}
      className="inline-flex h-32 items-center gap-8 rounded-pill border border-ivory/60 px-12 font-mono text-caption font-strong text-ivory"
    >
      {isLive ? <LiveIcon /> : <FixtureIcon />}
      <span>{modes.label}</span>
    </span>
  )
}
