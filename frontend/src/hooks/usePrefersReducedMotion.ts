import { useReducedMotion } from 'motion/react'

/**
 * True when the person has asked their device to reduce motion
 * (System Settings > Accessibility > Display > Reduce motion on macOS).
 *
 * Every animated part of the app asks this one hook, so honoring the setting
 * is decided in a single place.
 */
export function usePrefersReducedMotion(): boolean {
  // The library returns null until it has checked; treat that as "no".
  return useReducedMotion() === true
}
