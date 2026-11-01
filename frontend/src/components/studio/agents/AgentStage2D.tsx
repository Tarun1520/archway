import { motion, useReducedMotion } from 'motion/react'
import { studioAgentsCopy } from '../../../content/studio'
import { AGENTS, type AgentId, type TeamPicture } from '../../../lib/agentTeam'
import { Robot } from './Robot'

/** Where each robot stands, as a share of the stage (the lead in the middle). */
const SPOTS: Record<AgentId, { x: number; y: number }> = {
  lead: { x: 50, y: 46 },
  analyst: { x: 14, y: 20 },
  scout: { x: 50, y: 10 },
  judge: { x: 86, y: 20 },
  projects: { x: 14, y: 78 },
  reviewer: { x: 50, y: 86 },
  decider: { x: 86, y: 78 },
}

export const GLYPH: Record<AgentId, string> = {
  lead: 'L',
  analyst: 'A',
  scout: 'S',
  judge: 'J',
  projects: 'P',
  reviewer: 'R',
  decider: 'D',
}

const STAGE_W = 340
const STAGE_H = 210

/**
 * The flat stage: small drawn robots joined by lines, with a dot travelling
 * along a line when one agent messages another. Shown where 3D cannot run
 * (no WebGL); see AgentStage3D.tsx for the main stage.
 */
export function AgentStage2D({ team }: { team: TeamPicture }) {
  const reduceMotion = useReducedMotion()
  const latest = team.messages.at(-1) ?? null
  const point = (id: AgentId | 'team') => {
    const spot = SPOTS[id === 'team' ? 'lead' : id]
    return { x: (spot.x / 100) * STAGE_W, y: (spot.y / 100) * STAGE_H }
  }

  return (
    <div className="relative mx-auto" style={{ width: STAGE_W, height: STAGE_H + 36 }}>
      <svg aria-hidden="true" width={STAGE_W} height={STAGE_H} className="absolute inset-x-0 top-18">
        {AGENTS.filter((a) => a.id !== 'lead').map((a) => {
          const from = point('lead')
          const to = point(a.id)
          const hot = latest && (latest.from === a.id || latest.to === a.id)
          return (
            <line
              key={a.id}
              x1={from.x}
              y1={from.y}
              x2={to.x}
              y2={to.y}
              stroke={hot ? 'var(--color-vermilion)' : 'var(--color-line)'}
              strokeWidth={hot ? 1.5 : 1}
              strokeDasharray={team.agents[a.id].status === 'idle' ? '3 4' : undefined}
            />
          )
        })}
        {latest && !reduceMotion && latest.from !== latest.to && (
          <motion.rect
            key={latest.id}
            width={7}
            height={7}
            fill="var(--color-vermilion)"
            initial={{ x: point(latest.from).x - 3.5, y: point(latest.from).y - 3.5, opacity: 1 }}
            animate={{ x: point(latest.to).x - 3.5, y: point(latest.to).y - 3.5, opacity: [1, 1, 0] }}
            transition={{ duration: 1.1, ease: [0.25, 0, 0, 1] }}
          />
        )}
      </svg>

      {AGENTS.map((a) => {
        const agent = team.agents[a.id]
        const spot = point(a.id)
        return (
          <div
            key={a.id}
            role="img"
            aria-label={`${a.label}: ${agent.doing ?? studioAgentsCopy.status[agent.status]}`}
            title={`${a.role}. ${agent.doing ?? studioAgentsCopy.status[agent.status]}`}
            className="absolute flex -translate-x-1/2 flex-col items-center"
            style={{ left: spot.x, top: spot.y - 6 }}
          >
            <Robot glyph={GLYPH[a.id]} status={agent.status} size={a.id === 'lead' ? 42 : 34} />
            <span className={`mt-2 font-code text-[11px] uppercase tracking-[0.1em] ${agent.status === 'working' ? 'text-chalk' : 'text-smoke'}`}>
              {a.label}
              {a.id === 'scout' && agent.copies > 1 ? ` ×${agent.copies}` : ''}
            </span>
          </div>
        )
      })}
    </div>
  )
}
