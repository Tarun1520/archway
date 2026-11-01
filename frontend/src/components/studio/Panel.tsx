import type { ReactNode } from 'react'

interface PanelProps {
  /** The small heading at the top of the panel. */
  heading: string
  /** Optional extra content on the right of the heading (a label or a button). */
  aside?: ReactNode
  children: ReactNode
  className?: string
}

/**
 * A titled box: the building block of the studio's side columns.
 * It is a <section> with a heading, so screen readers can jump between panels.
 */
export function Panel({ heading, aside, children, className = '' }: PanelProps) {
  return (
    <section className={`flex min-h-0 flex-col rounded-card bg-graphite ${className}`}>
      <header className="flex min-h-44 items-center justify-between gap-8 border-b border-mist/10 px-16">
        <h2 className="text-caption font-strong tracking-wide text-ash uppercase">{heading}</h2>
        {aside}
      </header>
      <div className="min-h-0 flex-1 overflow-y-auto p-16">{children}</div>
    </section>
  )
}

/** The quiet sentence shown in a panel that has nothing to show yet. */
export function EmptyNote({ children }: { children: ReactNode }) {
  return <p className="text-body-sm text-ash">{children}</p>
}
