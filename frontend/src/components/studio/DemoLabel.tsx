import { studioCopy } from '../../content/studio'

/**
 * The label put on anything that is sample data.
 * Rule for the whole app: demo data must always be visibly marked as such.
 */
export function DemoLabel() {
  return (
    <span className="inline-flex h-20 items-center rounded-default border border-dashed border-ivory/60 px-6 font-mono text-caption text-ivory">
      {studioCopy.demoLabel}
    </span>
  )
}
