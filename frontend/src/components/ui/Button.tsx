import type { AnchorHTMLAttributes, ButtonHTMLAttributes } from 'react'
import { useGlow } from '../../hooks/useGlow'

/**
 * The button styles used across Archway.
 *
 *   primary  the glow pill: white, with a ring of slowly turning color that
 *            brightens and shifts as the pointer comes near. The ONE main
 *            action on a screen. Never decorative.
 *   ghost    ivory outline. Secondary actions on dark screens.
 *   outline  dark outline. Secondary actions on light screens.
 *
 * `Button` renders a <button> (it does something on this page).
 * `ButtonLink` renders an <a> (it goes somewhere). Both look the same.
 */
export type ButtonVariant = 'primary' | 'ghost' | 'outline'

/** "md" for the top bar and inline use, "lg" for the main call to action on a screen. */
export type ButtonSize = 'md' | 'lg'

const baseClasses =
  'inline-flex items-center justify-center gap-8 whitespace-nowrap rounded-control text-body font-normal transition-colors duration-200'

const sizeClasses: Record<ButtonSize, string> = {
  md: 'h-44 px-20',
  lg: 'h-60 px-28',
}

const variantClasses: Record<ButtonVariant, string> = {
  primary: 'glow-pill',
  ghost: 'border border-ivory text-ivory hover:bg-ivory/10',
  outline: 'border border-ink/25 text-ink hover:bg-ink/5',
}

/** Builds the class list for a variant and size. */
function buttonClasses(variant: ButtonVariant, size: ButtonSize, extra = ''): string {
  return `${baseClasses} ${sizeClasses[size]} ${variantClasses[variant]} ${extra}`.trim()
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
}

export function Button({ variant = 'primary', size = 'md', className, type = 'button', ...rest }: ButtonProps) {
  // Only the primary button glows; for the others the hook does nothing.
  const glowRef = useGlow<HTMLButtonElement>(variant === 'primary')
  return <button ref={glowRef} type={type} className={buttonClasses(variant, size, className)} {...rest} />
}

interface ButtonLinkProps extends AnchorHTMLAttributes<HTMLAnchorElement> {
  variant?: ButtonVariant
  size?: ButtonSize
}

export function ButtonLink({ variant = 'primary', size = 'md', className, ...rest }: ButtonLinkProps) {
  const glowRef = useGlow<HTMLAnchorElement>(variant === 'primary')
  return <a ref={glowRef} className={buttonClasses(variant, size, className)} {...rest} />
}
