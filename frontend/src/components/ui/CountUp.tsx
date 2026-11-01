import { useEffect, useRef, useState } from 'react'
import { animate, useInView } from 'motion/react'
import { usePrefersReducedMotion } from '../../hooks/usePrefersReducedMotion'

interface CountUpProps {
  /** The number to count up to. */
  value: number
  className?: string
}

/**
 * A number that counts up from zero the first time it scrolls into view.
 * With reduced motion on, the final number is shown straight away.
 */
export function CountUp({ value, className }: CountUpProps) {
  const reduceMotion = usePrefersReducedMotion()
  const numberRef = useRef<HTMLSpanElement>(null)

  // True once the number has been seen. `once` means it never flips back.
  const seen = useInView(numberRef, { once: true, margin: '0px 0px -15% 0px' })
  const [shown, setShown] = useState(0)

  useEffect(() => {
    if (!seen || reduceMotion) {
      return
    }
    // `animate` calls onUpdate many times a second with a number that eases from 0 to `value`.
    const controls = animate(0, value, {
      duration: 1.4,
      ease: [0.22, 1, 0.36, 1],
      onUpdate: (latest) => setShown(Math.round(latest)),
    })
    return () => controls.stop()
  }, [seen, reduceMotion, value])

  return (
    <span ref={numberRef} className={className}>
      {reduceMotion ? value : shown}
    </span>
  )
}
