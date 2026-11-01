import { useId } from 'react'

interface ArchyPortalProps {
  /** On: bright, with a beam of light. Off: a dim glow that slowly breathes. */
  active: boolean
  className?: string
}

/**
 * The portal Archy rises from: a dark two-layer platform, a glowing core, a
 * slowly turning ring of light ticks, and a beam of light going up.
 * Drawn in SVG (viewBox 240 x 90); the core's middle is at (120, 64).
 */
export function ArchyPortal({ active, className = '' }: ArchyPortalProps) {
  const id = useId().replace(/:/g, '') // unique names, so two portals on a page do not share gradients
  return (
    <svg viewBox="0 0 240 90" aria-hidden="true" className={`${className} ${active ? 'archy-portal-on' : 'archy-portal-off'}`}>
      <defs>
        <radialGradient id={`${id}-core`} cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#ffffff" />
          <stop offset="55%" stopColor="#e6f3ff" />
          <stop offset="85%" stopColor="#8fc2ff" />
          <stop offset="100%" stopColor="#3d6bff" stopOpacity="0" />
        </radialGradient>
        <linearGradient id={`${id}-beam`} x1="0" y1="1" x2="0" y2="0">
          <stop offset="0%" stopColor="#dbeeff" stopOpacity="0.85" />
          <stop offset="100%" stopColor="#dbeeff" stopOpacity="0" />
        </linearGradient>
        <linearGradient id={`${id}-plate`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#1d1f2b" />
          <stop offset="100%" stopColor="#0b0c12" />
        </linearGradient>
        <filter id={`${id}-glow`} x="-40%" y="-120%" width="180%" height="340%">
          <feGaussianBlur stdDeviation="5" />
        </filter>
      </defs>

      {/* The lower plate, with a blue-violet rim, then the upper plate. */}
      <ellipse cx="120" cy="74" rx="104" ry="15" fill="#0b0c12" stroke="#4a4fc4" strokeOpacity="0.7" strokeWidth="1.4" />
      <ellipse cx="120" cy="69" rx="96" ry="14" fill={`url(#${id}-plate)`} stroke="#2a2d48" strokeWidth="1" />

      {/* The beam (inside the portal's own picture; the tall beam behind the robot is drawn by the dock). */}
      <path d="M72 64 L168 64 L150 0 L90 0 Z" fill={`url(#${id}-beam)`} className="archy-portal-beam" />

      {/* The glow under the core, then the core itself. */}
      <ellipse cx="120" cy="64" rx="64" ry="13" fill="#9ccaff" filter={`url(#${id}-glow)`} className="archy-portal-halo" />
      <ellipse cx="120" cy="64" rx="52" ry="9.5" fill={`url(#${id}-core)`} className="archy-portal-core" />

      {/* The ring of ticks, turning slowly. */}
      <ellipse cx="120" cy="64" rx="70" ry="13.5" fill="none" stroke="#f2f8ff" strokeWidth="2.6" strokeDasharray="3 7" className="archy-portal-ticks" />
    </svg>
  )
}
