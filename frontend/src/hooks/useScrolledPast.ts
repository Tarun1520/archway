import { useEffect, useState } from 'react'

/**
 * Returns true once the page has been scrolled further than `offset` pixels.
 * The top bar uses it to switch from transparent to frosted glass.
 */
export function useScrolledPast(offset: number): boolean {
  const [scrolledPast, setScrolledPast] = useState(false)

  useEffect(() => {
    const update = () => setScrolledPast(window.scrollY > offset)

    update()
    // `passive` promises the browser we will not block scrolling.
    window.addEventListener('scroll', update, { passive: true })
    return () => window.removeEventListener('scroll', update)
  }, [offset])

  return scrolledPast
}
