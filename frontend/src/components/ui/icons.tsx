import type { ReactNode } from 'react'

/**
 * Small line icons, drawn in the current text color.
 *
 * They are decorative: each one sits next to text that says the same thing,
 * so they are hidden from screen readers with `aria-hidden`.
 */
function IconFrame({ size = 24, children }: { size?: number; children: ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {children}
    </svg>
  )
}

interface IconProps {
  size?: number
}

/** Two chain links: a claim connected to its source. */
export function SourceIcon({ size }: IconProps) {
  return (
    <IconFrame size={size}>
      <path d="M10 14a4 4 0 0 0 5.66 0l3-3a4 4 0 0 0-5.66-5.66l-1 1" />
      <path d="M14 10a4 4 0 0 0-5.66 0l-3 3a4 4 0 0 0 5.66 5.66l1-1" />
    </IconFrame>
  )
}

/** A shield with a check: fixed rules that hold. */
export function RulesIcon({ size }: IconProps) {
  return (
    <IconFrame size={size}>
      <path d="M12 3 5 6v5.5c0 4.2 2.8 7.6 7 9.5 4.2-1.9 7-5.3 7-9.5V6l-7-3Z" />
      <path d="m9 12 2.2 2.2L15.2 10" />
    </IconFrame>
  )
}

/** A dashed circle: something not known yet, shown as not known. */
export function UnknownIcon({ size }: IconProps) {
  return (
    <IconFrame size={size}>
      <circle cx="12" cy="12" r="8.5" strokeDasharray="3.2 3.2" />
      <path d="M12 8.5v4" />
      <path d="M12 15.5h.01" />
    </IconFrame>
  )
}

/** A check inside a circle: something was done. */
export function CheckIcon({ size }: IconProps) {
  return (
    <IconFrame size={size}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="m8.5 12.2 2.4 2.4 4.6-5" />
    </IconFrame>
  )
}

/** An exclamation mark inside a circle: something needs attention. */
export function AlertIcon({ size }: IconProps) {
  return (
    <IconFrame size={size}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 7.5v5.5" />
      <path d="M12 16.2h.01" />
    </IconFrame>
  )
}

/** A steering wheel: the person stays in control. */
export function SteerIcon({ size }: IconProps) {
  return (
    <IconFrame size={size}>
      <circle cx="12" cy="12" r="8.5" />
      <circle cx="12" cy="12" r="2" />
      <path d="M12 14v6.5" />
      <path d="m10.3 11-6.3-2.2" />
      <path d="m13.7 11 6.3-2.2" />
    </IconFrame>
  )
}

/** A bookmark: the place is kept. */
export function ResumeIcon({ size }: IconProps) {
  return (
    <IconFrame size={size}>
      <path d="M7 4h10v16l-5-3.5L7 20V4Z" />
    </IconFrame>
  )
}

/** A four-point sparkle: marks anything the model wrote, so it is never mistaken for the user's words. */
export function SparkleIcon({ size }: IconProps) {
  return (
    <IconFrame size={size}>
      <path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9L12 3z" />
      <path d="M19 15l.7 1.8L21.5 17.5l-1.8.7L19 20l-.7-1.8-1.8-.7 1.8-.7L19 15z" />
    </IconFrame>
  )
}

// --- Studio sidebar and nav --------------------------------------------------

/** A light bulb: the idea step. */
export function IdeaIcon({ size }: IconProps) {
  return (
    <IconFrame size={size}>
      <path d="M9 18h6M10 21h4" />
      <path d="M12 3a6 6 0 0 0-3.5 10.9c.6.4.9 1 .9 1.6V16h5.2v-.5c0-.6.3-1.2.9-1.6A6 6 0 0 0 12 3z" />
    </IconFrame>
  )
}

/** A speech bubble with a question mark: the questions step. */
export function QuestionIcon({ size }: IconProps) {
  return (
    <IconFrame size={size}>
      <path d="M4 5h16v11H9l-5 4V5z" />
      <path d="M10 9a2 2 0 1 1 2.8 1.8c-.5.3-.8.7-.8 1.2M12 14h.01" />
    </IconFrame>
  )
}

/** A page with lines: the brief step. */
export function DocumentIcon({ size }: IconProps) {
  return (
    <IconFrame size={size}>
      <path d="M14 3H6v18h12V7l-4-4z" />
      <path d="M14 3v4h4M9 12h6M9 16h6" />
    </IconFrame>
  )
}

/** A magnifying glass: the research step. */
export function SearchIcon({ size }: IconProps) {
  return (
    <IconFrame size={size}>
      <circle cx="11" cy="11" r="6" />
      <path d="M20 20l-4.5-4.5" />
    </IconFrame>
  )
}

/** A list with ticks: the shortlist step. */
export function ListCheckIcon({ size }: IconProps) {
  return (
    <IconFrame size={size}>
      <path d="M4 6l1.5 1.5L8 5M4 13l1.5 1.5L8 12M11 6.5h9M11 13.5h9M4 19.5h16" />
    </IconFrame>
  )
}

/** Branching paths: the options step (one idea, several ways to build it). */
export function OptionsIcon({ size }: IconProps) {
  return (
    <IconFrame size={size}>
      <path d="M12 4v5M12 9L6 15M12 9l6 6M6 15v5M18 15v5M12 9v11" />
    </IconFrame>
  )
}

/** A numbered list leading to a flag: the build plan. */
export function PlanIcon({ size }: IconProps) {
  return (
    <IconFrame size={size}>
      <path d="M4 6h2M4 12h2M4 18h2M9 6h7M9 12h5M9 18h3M17 14v7M17 14h4l-1 1.5 1 1.5h-4" />
    </IconFrame>
  )
}

/** A folder: the projects group. */
export function FolderIcon({ size }: IconProps) {
  return (
    <IconFrame size={size}>
      <path d="M3 6h6l2 2h10v11H3V6z" />
    </IconFrame>
  )
}

/** A chevron pointing up (rotate it to point down). */
export function ChevronIcon({ size }: IconProps) {
  return (
    <IconFrame size={size}>
      <path d="M6 15l6-6 6 6" />
    </IconFrame>
  )
}

/** A plus sign. */
export function PlusIcon({ size }: IconProps) {
  return (
    <IconFrame size={size}>
      <path d="M12 5v14M5 12h14" />
    </IconFrame>
  )
}

/** Three lines: opens the sidebar on small screens. */
export function MenuIcon({ size }: IconProps) {
  return (
    <IconFrame size={size}>
      <path d="M4 7h16M4 12h16M4 17h16" />
    </IconFrame>
  )
}

/** A bin: delete. */
export function TrashIcon({ size }: IconProps) {
  return (
    <IconFrame size={size}>
      <path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13" />
    </IconFrame>
  )
}

/** A window with a side panel: folds or opens the sidebar. */
export function SidebarIcon({ size }: IconProps) {
  return (
    <IconFrame size={size}>
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M9 4v16" />
    </IconFrame>
  )
}
