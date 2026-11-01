import { studioCopy } from '../../content/studio'
import { useDemoEvents } from '../../hooks/useDemoEvents'
import type { StreamEvent } from '../../lib/api/types'
import type { FeedLine } from '../../lib/workflowProgress'
import { AlertIcon } from '../ui/icons'
import { DemoLabel } from './DemoLabel'
import { EmptyNote, Panel } from './Panel'

/** Turns one DEMO stream event into a line of text. */
function describeDemo(event: StreamEvent): string {
  if (event.data.message) return event.data.message
  const node = event.data.node ?? 'unknown step'
  if (event.name === 'node_started') return `${node}: started`
  if (event.name === 'node_finished') return `${node}: finished`
  return `${node}: ${event.name}`
}

interface ActivityFeedProps {
  /** Lines from the REAL run of the selected project. Empty when there is no run. */
  lines: FeedLine[]
  hasRun: boolean
}

/**
 * The activity feed: a running list of what the workflow has done.
 *
 * When the project has a run, it shows that run's real, saved events and
 * nothing else. When there is no run yet, it offers the backend's SAMPLE
 * stream, and every sample line sits under a "Demo data" label. Real and
 * sample lines are never mixed.
 */
export function ActivityFeed({ lines, hasRun }: ActivityFeedProps) {
  const demo = useDemoEvents()
  const showingDemo = !hasRun && demo.events.length > 0

  return (
    <Panel heading={studioCopy.activityHeading} aside={showingDemo ? <DemoLabel /> : undefined} className="flex-1">
      {hasRun ? (
        // role="log" tells screen readers this list grows over time.
        <ol role="log" aria-label={studioCopy.activityHeading} className="flex flex-col gap-8">
          {lines.length === 0 && <li className="text-body-sm text-ash">{studioCopy.loading}</li>}
          {lines.map((line) => (
            <li key={line.id} className="flex items-start gap-8 text-body-sm text-ivory">
              <span className="mt-2 w-24 shrink-0 font-mono text-caption text-ash">{line.id}</span>
              {line.isError && (
                <span className="mt-2 shrink-0" title={studioCopy.errorLabel}>
                  <AlertIcon size={14} />
                </span>
              )}
              <span>
                {line.isError && <span className="font-strong">{studioCopy.errorLabel}: </span>}
                {line.text}
              </span>
            </li>
          ))}
        </ol>
      ) : (
        <>
          {!showingDemo && demo.status !== 'failed' && <EmptyNote>{studioCopy.activityEmpty}</EmptyNote>}
          {demo.status === 'failed' && <EmptyNote>{studioCopy.activityFailed}</EmptyNote>}
          <ol role="log" aria-label={studioCopy.activityHeading} className="flex flex-col gap-8">
            {demo.events.map((event) => (
              <li key={event.id} className="flex items-start gap-8 text-body-sm text-ivory">
                <span className="mt-2 font-mono text-caption text-ash">{event.id.padStart(2, '0')}</span>
                <span>{describeDemo(event)}</span>
              </li>
            ))}
          </ol>
          <button
            type="button"
            onClick={demo.play}
            disabled={demo.status === 'playing'}
            className="mt-16 h-36 rounded-control border border-mist/25 px-16 text-body-sm text-ivory hover:bg-ivory/10 disabled:opacity-60"
          >
            {showingDemo ? studioCopy.activityReplay : studioCopy.activityPlay}
          </button>
        </>
      )}
    </Panel>
  )
}
