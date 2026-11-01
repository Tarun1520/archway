import { studioCopy } from '../../content/studio'
import type { SuggestionsState } from '../../hooks/useSuggestions'
import type { BriefSuggestions } from '../../lib/api/types'
import { useGlow } from '../../hooks/useGlow'
import { SparkleIcon } from '../ui/icons'

/** One suggestion, ready to show. `tag` says where it will go (for example "Budget"). */
export interface SuggestionRow {
  id: string
  text: string
  reason: string | null
  tag?: string
  actionLabel?: string
  /** A generic option written by code, not by the model: shown without the sparkle. */
  standard?: boolean
}

interface AiSuggestionsProps {
  /** The block these are for, used in the accessible name ("AI suggestions for Must have"). */
  forBlock: string
  state: SuggestionsState
  onRetry: () => void
  rows: SuggestionRow[]
  onAdd: (row: SuggestionRow) => void
  /** Shown when the model had nothing to add for this block. */
  emptyText?: string
  /** Hide the "who wrote this" line (used when several panels sit close together). */
  quietSource?: boolean
}

/** Says honestly who wrote the suggestions. */
function Source({ data }: { data: BriefSuggestions }) {
  if (data.mode === 'fixture') return <>{studioCopy.aiSourceFixture}</>
  return <>{data.model ? `${studioCopy.aiSourceLive} ${data.model}` : studioCopy.aiSourceLiveUnknown}</>
}

/**
 * A panel of ideas written by the model.
 *
 * It is made to look like what it is. The sparkle, the "AI suggestion" label
 * and the lighter, dotted frame mean "the model wrote this" at a glance, apart
 * from the user's own words (plain rows) and Archway's assumptions (dashed
 * cards). Nothing in it is part of the brief until the user presses Add.
 *
 * It GLOWS like the welcome page's main button (`ai-glow` in
 * styles/index.css): a turning ring of color and a soft halo, brighter as the
 * pointer comes near (useGlow). The sparkles turn through the same colors.
 */
export function AiSuggestions({ forBlock, state, onRetry, rows, onAdd, emptyText, quietSource = false }: AiSuggestionsProps) {
  const glowRef = useGlow<HTMLElement>()
  return (
    <aside
      ref={glowRef}
      aria-label={`${studioCopy.aiLabel}: ${forBlock}`}
      className="ai-glow flex flex-col gap-10 rounded-card p-12"
    >
      <header className="flex flex-wrap items-center gap-8 text-ivory">
        <span className="ai-sparkle inline-flex">
          <SparkleIcon size={16} />
        </span>
        <span className="font-mono text-caption tracking-wide uppercase">{studioCopy.aiLabel}</span>
        {state.status === 'ready' && !quietSource && (
          <span className="text-caption text-ash">
            <Source data={state.data} />
          </span>
        )}
      </header>

      {state.status === 'loading' && (
        <div role="status" className="flex flex-col gap-8">
          <span className="text-caption text-ash">{studioCopy.aiReading}</span>
          {[88, 72, 80].map((width) => (
            <span key={width} className="ai-shimmer block h-16 rounded-default" style={{ width: `${width}%` }} />
          ))}
        </div>
      )}

      {state.status === 'error' && (
        <div role="alert" className="flex flex-col items-start gap-8 text-caption text-ash">
          <span>
            {studioCopy.aiUnavailable} {state.message}
          </span>
          <button
            type="button"
            onClick={onRetry}
            className="h-32 rounded-control border border-mist/25 px-12 text-caption text-ivory hover:bg-ivory/10"
          >
            {studioCopy.aiRetry}
          </button>
        </div>
      )}

      {state.status === 'ready' && rows.length === 0 && (
        <p className="text-caption text-ash">{emptyText ?? studioCopy.aiNothingMore}</p>
      )}

      {state.status === 'ready' && rows.some((row) => row.standard) && (
        <button
          type="button"
          onClick={onRetry}
          className="h-32 self-start rounded-control border border-mist/25 px-12 text-caption text-ivory hover:bg-ivory/10"
        >
          {studioCopy.aiAskAgain}
        </button>
      )}

      {state.status === 'ready' && rows.length > 0 && (
        <ul className="flex flex-col gap-8">
          {rows.map((row) => (
            <li key={row.id} className="flex items-start gap-8 rounded-default bg-obsidian/60 p-8">
              <span className={`mt-2 inline-flex w-14 shrink-0 ${row.standard ? '' : 'ai-sparkle'}`}>
                {row.standard ? null : <SparkleIcon size={14} />}
              </span>
              <div className="min-w-0 flex-1">
                {row.standard && (
                  <span className="mr-6 mb-4 inline-flex h-20 items-center rounded-default border border-mist/25 px-6 font-mono text-caption text-ash">
                    {studioCopy.aiStandard}
                  </span>
                )}
                {row.tag && (
                  <span className="mb-4 inline-flex h-20 items-center rounded-default border border-ivory/40 px-6 font-mono text-caption text-ivory">
                    {row.tag}
                  </span>
                )}
                <p className="text-body-sm text-ivory">{row.text}</p>
                {row.reason && <p className="mt-2 text-caption text-ash">{row.reason}</p>}
              </div>
              <button
                type="button"
                aria-label={`${row.actionLabel ?? studioCopy.aiAdd}: ${row.text}`}
                onClick={() => onAdd(row)}
                className="h-32 shrink-0 rounded-control border border-mist/25 px-12 text-caption text-ivory hover:bg-ivory/10"
              >
                {row.actionLabel ?? studioCopy.aiAdd}
              </button>
            </li>
          ))}
        </ul>
      )}
    </aside>
  )
}
