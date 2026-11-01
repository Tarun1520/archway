import type { ReactNode } from 'react'

interface TagProps {
  children: ReactNode
  /** "night" for dark screens (the default), "morning" for the light ones, "forest" for the deep green bands. */
  tone?: 'night' | 'morning' | 'forest'
}

const toneClasses = {
  night: 'border-mist/25 text-ash',
  morning: 'border-ink/15 bg-white/60 text-stone',
  forest: 'border-white/25 text-sage',
}

/** A small pill label that sits above a headline and names the section. */
export function Tag({ children, tone = 'night' }: TagProps) {
  return (
    <span className={`inline-flex h-28 items-center rounded-pill border px-12 text-caption font-strong ${toneClasses[tone]}`}>
      {children}
    </span>
  )
}
