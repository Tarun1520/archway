import type { HTMLAttributes } from 'react'

/**
 * The graphite card: the standard surface for grouping content.
 *
 * It has no shadow and no border on purpose. It stands out only because it is
 * one step lighter than the page behind it.
 */
export function Card({ className = '', ...rest }: HTMLAttributes<HTMLDivElement>) {
  return <div className={`rounded-card bg-graphite p-24 md:p-32 ${className}`.trim()} {...rest} />
}
