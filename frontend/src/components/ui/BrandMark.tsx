/**
 * The Archway logo: an arch with a smaller arch inside it.
 * It is decorative (the word "Archway" always sits beside it), so it is hidden
 * from screen readers.
 */
export function BrandMark({ size = 24 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      aria-hidden="true"
    >
      <path d="M4 21V11a8 8 0 0 1 16 0v10" strokeWidth="1.75" />
      <path d="M8.75 21v-9.75a3.25 3.25 0 0 1 6.5 0V21" strokeWidth="1.25" strokeOpacity="0.5" />
    </svg>
  )
}
