import type { AgentStatus } from '../../../lib/agentTeam'

interface RobotProps {
  /** The letter on its chest, so the robots are easy to tell apart. */
  glyph: string
  status: AgentStatus
  size?: number
}

/**
 * One small robot, drawn in sharp lines to match the studio.
 *
 *   idle     dim grey lines, eyes still
 *   working  white lines, the antenna light blinks in the accent, the eyes scan
 *            and the body bobs (all switched off for reduced motion)
 *   done     white lines, eyes closed in a contented "^ ^"
 *
 * The animation classes live in styles/index.css (.bot-working ...).
 */
export function Robot({ glyph, status, size = 44 }: RobotProps) {
  const working = status === 'working'
  const stroke = status === 'idle' ? 'var(--color-slate)' : 'var(--color-chalk)'
  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size * (56 / 48)}
      viewBox="0 0 48 56"
      className={working ? 'bot-working' : ''}
      fill="none"
      stroke={stroke}
      strokeWidth={1.5}
    >
      <g className="bot-body">
        {/* Antenna, with its light. */}
        <line x1="24" y1="5" x2="24" y2="11" />
        <rect
          className="bot-antenna"
          x="21.5"
          y="1"
          width="5"
          height="5"
          fill={working ? 'var(--color-vermilion)' : status === 'done' ? 'var(--color-chalk)' : 'none'}
          stroke={working ? 'var(--color-vermilion)' : stroke}
        />
        {/* Head. */}
        <rect x="8" y="11" width="32" height="22" fill="var(--color-carbon)" />
        {status === 'done' ? (
          <path d="M15 24l3-3 3 3M27 24l3-3 3 3" strokeLinecap="square" />
        ) : (
          <g className="bot-eyes">
            <rect x="15" y="18" width="5" height="7" fill={working ? 'var(--color-chalk)' : 'none'} />
            <rect x="28" y="18" width="5" height="7" fill={working ? 'var(--color-chalk)' : 'none'} />
          </g>
        )}
        <line x1="19" y1="29" x2="29" y2="29" />
        {/* Body with its letter, and two short arms. */}
        <rect x="13" y="36" width="22" height="16" fill="var(--color-carbon)" />
        <line x1="13" y1="41" x2="7" y2="45" />
        <line x1="35" y1="41" x2="41" y2="45" />
        <text
          x="24"
          y="48"
          textAnchor="middle"
          fontFamily="var(--font-code)"
          fontSize="9"
          fontWeight="600"
          fill={working ? 'var(--color-vermilion)' : stroke}
          stroke="none"
        >
          {glyph}
        </text>
      </g>
    </svg>
  )
}
