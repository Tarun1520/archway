import type { ReactNode } from 'react'
import { motion } from 'motion/react'
import { usePrefersReducedMotion } from '../../hooks/usePrefersReducedMotion'

interface RevealProps {
  children: ReactNode
  /** Seconds to wait before starting. Use small steps (0.08) to stagger a row. */
  delay?: number
  /**
   * By default an element is revealed once it is a little way above the
   * bottom edge of the window. Set this for elements that sit AT the bottom
   * edge (they would otherwise wait for a scroll that may never come).
   */
  revealAtEdge?: boolean
  className?: string
}

/**
 * Fades its children in and lifts them slightly the first time they scroll
 * into view. With reduced motion on, the children are simply shown.
 */
export function Reveal({ children, delay = 0, revealAtEdge = false, className }: RevealProps) {
  const reduceMotion = usePrefersReducedMotion()

  if (reduceMotion) {
    return <div className={className}>{children}</div>
  }

  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: revealAtEdge ? '0px' : '0px 0px -10% 0px' }}
      transition={{ duration: 0.8, delay, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </motion.div>
  )
}
