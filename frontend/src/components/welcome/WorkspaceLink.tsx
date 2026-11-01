import type { MouseEvent } from 'react'
import { start } from '../../content/welcome'
import { useGoToWorkspace } from '../../hooks/useGoToWorkspace'
import { STUDIO_HASH } from '../../lib/hashRoute'

/**
 * "Continue in workspace": the quiet second way into the studio, for picking
 * up a project that was already begun. It is a link (it goes somewhere), not a
 * form action, and it starts nothing new.
 *
 * Designed to sit under the main glowing "Start a project" button without
 * competing with it: a frosted pill with a small panel icon on the left and an
 * arrow that slides forward on hover. Motion is switched off for people who
 * asked their system for reduced motion.
 *
 * A plain click goes through the space transition. A click with a modifier
 * key (open in a new tab, and so on) is left to the browser, as for any link.
 */
export function WorkspaceLink() {
  const goToWorkspace = useGoToWorkspace()
  const onClick = (event: MouseEvent<HTMLAnchorElement>) => {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
    event.preventDefault()
    goToWorkspace()
  }
  return (
    <a
      href={STUDIO_HASH}
      onClick={onClick}
      className="group inline-flex h-48 items-center gap-12 rounded-control border border-ink/15 bg-white/55 pl-8 pr-20 text-body text-ink shadow-[0_1px_0_rgba(255,255,255,0.8)_inset,0_6px_18px_-10px_rgba(28,34,44,0.35)] backdrop-blur-md transition duration-200 hover:-translate-y-[2px] hover:border-cobalt/50 hover:bg-white hover:shadow-[0_10px_24px_-12px_rgba(82,102,235,0.55)] focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-cobalt motion-reduce:transition-none motion-reduce:hover:translate-y-0"
    >
      {/* The panel icon sits in its own small chip, so the label reads as one calm line. */}
      <span
        aria-hidden="true"
        className="inline-flex size-32 items-center justify-center rounded-pill bg-cobalt/10 text-cobalt transition-colors duration-200 group-hover:bg-cobalt group-hover:text-white"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <rect x="3" y="4" width="18" height="16" rx="3" />
          <path d="M9 4v16" />
          <path d="M13 9h4M13 13h4" />
        </svg>
      </span>

      <span>{start.continueLabel}</span>

      <svg
        aria-hidden="true"
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="text-stone transition duration-200 group-hover:translate-x-4 group-hover:text-cobalt motion-reduce:transition-none motion-reduce:group-hover:translate-x-0"
      >
        <path d="M5 12h14M13 6l6 6-6 6" />
      </svg>
    </a>
  )
}
