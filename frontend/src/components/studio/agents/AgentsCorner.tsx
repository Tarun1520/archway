import { useEffect, useState } from 'react'
import { studioAgentsCopy } from '../../../content/studio'
import { AGENTS, type TeamPicture } from '../../../lib/agentTeam'
import { GLYPH } from './AgentStage2D'
import { AgentStage3D } from './AgentStage3D'
import { AgentThoughts } from './AgentThoughts'
import { Robot } from './Robot'

/**
 * The agents corner: the research team drawn as small robots, live.
 *
 * The robots are 3D (AgentStage3D): each lights up when its agent really
 * works (from the run's events), and when one agent messages another the
 * sender walks over and plugs a cable into the recipient. Below the robots,
 * "Thinking" says in simple words what they are doing, and the newest message
 * is written out. It can be folded down to a single strip of small robots.
 * Screen readers get the thoughts and messages as text instead of the animation.
 */
interface AgentsCornerProps {
  team: TeamPicture
  /** The robots come onto the stage, each in its own way (once, when the team first appears). */
  entrance?: boolean
  onEntered?: () => void
  /** The robots leave the stage; `onLeft` is called once they are gone. */
  leaving?: boolean
  onLeft?: () => void
}

export function AgentsCorner({ team, entrance, onEntered, leaving = false, onLeft }: AgentsCornerProps) {
  // Open by itself while the team works, folded when it is quiet; once the
  // person opens or folds it, their choice wins. (Docked beside the content on
  // wide screens, where there is room, it always stays open.)
  const [choice, setChoice] = useState<boolean | null>(null)
  const wide = useWide()
  const open = wide || (choice ?? team.live)
  const setOpen = (value: boolean) => setChoice(value)
  const state = team.designing ? studioAgentsCopy.designing : team.live ? studioAgentsCopy.live : team.started ? studioAgentsCopy.done : studioAgentsCopy.ready
  // Folded, there is no stage to leave from: the page moves on at once.
  useEffect(() => {
    if (leaving && !open) onLeft?.()
  }, [leaving, open]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <aside
      aria-label={studioAgentsCopy.heading}
      // Docked beside the content (xl) there is no box at all: the robots and
      // their thoughts sit straight on the page, so they get all the room.
      // Smaller screens float it over the page, so it keeps a background there.
      className="fixed inset-x-0 bottom-0 z-40 max-h-[85dvh] overflow-y-auto rounded-t-card bg-carbon/95 px-12 backdrop-blur-md sm:inset-x-auto sm:right-24 sm:bottom-24 sm:w-[400px] sm:rounded-card xl:sticky xl:top-88 xl:right-auto xl:bottom-auto xl:max-h-none xl:w-full xl:overflow-visible xl:rounded-none xl:bg-transparent xl:px-0 xl:backdrop-blur-none"
    >
      <header className="flex items-center justify-between gap-12 px-4 py-12">
        <p className="flex items-center gap-10 font-code text-label uppercase text-chalk">
          <span
            aria-hidden="true"
            className={`inline-block size-8 ${team.live ? 'live-dot bg-vermilion' : team.started ? 'bg-chalk' : 'bg-slate'}`}
          />
          {studioAgentsCopy.heading}
          <span className="text-smoke">· {state}</span>
        </p>
        <button
          type="button"
          hidden={wide}
          onClick={() => setOpen(!open)}
          aria-expanded={open}
          className="min-h-44 px-8 font-code text-label uppercase text-smoke transition-colors duration-150 hover:text-chalk focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-vermilion"
        >
          {open ? studioAgentsCopy.fold : studioAgentsCopy.unfold}
        </button>
      </header>

      {/* Folded: one strip of small robots. */}
      {!open && (
        <ul className="flex items-end justify-between gap-4 px-4 pb-12">
          {AGENTS.map((a) => (
            <li key={a.id} title={`${a.label}: ${team.agents[a.id].doing ?? studioAgentsCopy.status[team.agents[a.id].status]}`}>
              <Robot glyph={GLYPH[a.id]} status={team.agents[a.id].status} size={26} />
            </li>
          ))}
        </ul>
      )}

      {open && (
        <div>
          {/* The stage: 3D robots, the lead in the middle, the specialists around it. */}
          <AgentStage3D team={team} height={wide ? 380 : 320} entrance={entrance} onEntered={onEntered} leaving={leaving} onLeft={onLeft} />

          {/* Below the robots: their thoughts and messages, as a running stream. */}
          <AgentThoughts team={team} />
        </div>
      )}
    </aside>
  )
}


/** True on screens wide enough to dock the team beside the content (Tailwind's xl, 1280px). */
function useWide(): boolean {
  const query = '(min-width: 1280px)'
  const [wide, setWide] = useState(() => typeof window !== 'undefined' && window.matchMedia(query).matches)
  useEffect(() => {
    const media = window.matchMedia(query)
    const update = () => setWide(media.matches)
    media.addEventListener('change', update)
    return () => media.removeEventListener('change', update)
  }, [])
  return wide
}
