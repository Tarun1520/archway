import { studioUi } from '../../../content/studio'
import type { ResearchSnapshot } from '../../../lib/api/types'
import type { FeedLine } from '../../../lib/workflowProgress'
import { LiveNumber } from './LiveNumber'

/**
 * The research, while it runs: four big numbers that climb as the agents
 * work, and one line saying what is happening now. The robots in the corner
 * show who is doing it.
 */
export function ResearchLive({ research, feed }: { research: ResearchSnapshot | null; feed: FeedLine[] }) {
  const stats = [
    { label: studioUi.stats.capabilities, value: research?.capabilities.length ?? 0 },
    { label: studioUi.stats.found, value: research?.components.length ?? 0 },
    { label: studioUi.stats.sources, value: research?.evidence.length ?? 0 },
    { label: studioUi.stats.decisions, value: (research?.receipts ?? []).filter((r) => r.final_result).length },
  ]
  const now = [...feed].reverse().find((line) => !line.text.startsWith('Model call') && !line.text.startsWith('GitHub request'))

  return (
    <section className="flex flex-col gap-48">
      <dl className="grid grid-cols-2 border-t border-line md:grid-cols-4">
        {stats.map((stat) => (
          <div key={stat.label} className="border-b border-line py-24 pr-16 md:border-r md:pl-16 md:first:pl-0 md:last:border-r-0">
            <dt className="font-code text-label uppercase text-smoke">{stat.label}</dt>
            <dd className="mt-8 font-code text-h1 font-semibold tracking-[-0.04em] text-chalk">
              <LiveNumber value={stat.value} />
            </dd>
          </div>
        ))}
      </dl>
      {now && (
        <p className="max-w-3xl text-lead text-chalk" aria-live="polite">
          <span className="mr-12 font-code text-label uppercase text-vermilion">{studioUi.now}</span>
          {now.text}
        </p>
      )}
    </section>
  )
}
