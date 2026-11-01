import { animate } from 'motion/react'
import { useEffect, useRef, useState } from 'react'
import { usePrefersReducedMotion } from '../../../hooks/usePrefersReducedMotion'

/**
 * A number that climbs from its last value to its new one whenever it changes
 * (live counters). Unlike CountUp it never restarts from zero.
 */
export function LiveNumber({ value }: { value: number }) {
  const reduceMotion = usePrefersReducedMotion()
  const [shown, setShown] = useState(value)
  const last = useRef(value)

  useEffect(() => {
    if (reduceMotion) {
      last.current = value
      return
    }
    const controls = animate(last.current, value, {
      duration: 0.6,
      ease: [0.25, 0, 0, 1],
      onUpdate: (latest) => setShown(Math.round(latest)),
    })
    last.current = value
    return () => controls.stop()
  }, [value, reduceMotion])

  return <span>{reduceMotion ? value : shown}</span>
}
