import type { ReactNode } from 'react'

interface SectionProps {
  /** Lets links like "#principles" jump to this section. */
  id?: string
  children: ReactNode
  className?: string
}

/**
 * The standard wrapper for a block of the page below the hero.
 * It gives every section the same side padding, the same vertical rhythm, and
 * the same maximum content width, so sections line up with each other.
 */
export function Section({ id, children, className = '' }: SectionProps) {
  return (
    <section id={id} className={`px-20 py-56 md:px-32 md:py-72 ${className}`.trim()}>
      <div className="mx-auto max-w-page">{children}</div>
    </section>
  )
}
