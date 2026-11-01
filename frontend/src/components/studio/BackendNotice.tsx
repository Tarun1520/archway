import { studioCopy } from '../../content/studio'
import { AlertIcon } from '../ui/icons'

/**
 * Shown when the backend cannot be reached.
 * It says what is wrong and exactly how to fix it, instead of leaving the
 * studio looking empty for no visible reason.
 */
export function BackendNotice({ reason }: { reason: string }) {
  return (
    <div role="alert" className="mx-20 mt-12 flex items-start gap-12 rounded-card border border-ivory/40 bg-graphite p-16">
      <span className="mt-2 shrink-0 text-ivory">
        <AlertIcon size={18} />
      </span>
      <div className="min-w-0">
        <p className="text-body font-strong text-ivory">{studioCopy.backendDownTitle}</p>
        <p className="mt-4 text-body-sm text-ash">{studioCopy.backendDownText}</p>
        <code className="mt-8 block overflow-x-auto rounded-default bg-obsidian px-12 py-8 font-mono text-body-sm text-ivory">
          {studioCopy.backendStartCommand}
        </code>
        <p className="mt-8 font-mono text-caption text-ash">{reason}</p>
      </div>
    </div>
  )
}
