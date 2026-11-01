import { useReducedMotion } from 'motion/react'
import type { ButtonHTMLAttributes } from 'react'
import { NoiseBackground } from './NoiseBackground'

/**
 * The studio's buttons: a pill with a frame of slowly drifting colour and a
 * fine grain around it (NoiseBackground, from Aceternity UI), and a dark face
 * with the label on it.
 *
 *   primary  the main action on a screen: warm vermilion and amber.
 *   outline  a secondary action: cool grey-blue, the same pill, quieter.
 *   ghost    a small, low-key action: the same quiet colours, a little tighter.
 *
 * Every variant: 44px minimum touch height, a 2px accent focus ring, a small
 * press, and no drifting colour while disabled or when reduced motion is on.
 */
export type StudioButtonVariant = 'primary' | 'outline' | 'ghost'

interface StudioButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: StudioButtonVariant
}

const COLOURS: Record<StudioButtonVariant, string[]> = {
  primary: ['rgb(255, 61, 0)', 'rgb(255, 150, 70)', 'rgb(255, 205, 120)'],
  outline: ['rgb(120, 130, 160)', 'rgb(190, 195, 215)', 'rgb(90, 105, 140)'],
  ghost: ['rgb(120, 130, 160)', 'rgb(190, 195, 215)', 'rgb(90, 105, 140)'],
}

const FACE =
  'flex min-h-44 w-full cursor-pointer items-center justify-center gap-10 whitespace-nowrap rounded-pill ' +
  'bg-linear-to-r from-[#060606] via-[#060606] to-[#171717] font-tight text-[14px] font-semibold uppercase tracking-[0.1em] text-chalk ' +
  'shadow-[0px_1px_0px_0px_#000_inset,0px_1px_0px_0px_#2a2a2a] transition-transform duration-100 ' +
  'active:scale-[0.98] focus-visible:outline-none disabled:cursor-not-allowed'

export function StudioButton({ variant = 'primary', className = '', type = 'button', disabled, children, ...rest }: StudioButtonProps) {
  const reduceMotion = useReducedMotion()
  return (
    <span
      className={`inline-flex w-fit rounded-pill has-[button:focus-visible]:outline-2 has-[button:focus-visible]:outline-offset-2 has-[button:focus-visible]:outline-vermilion ${
        disabled ? 'opacity-50' : ''
      } ${className}`}
    >
      <NoiseBackground
        containerClassName="w-full rounded-pill p-3"
        gradientColors={COLOURS[variant]}
        noiseIntensity={variant === 'primary' ? 0.28 : 0.2}
        animating={!disabled && !reduceMotion}
      >
        <button type={type} disabled={disabled} className={`${FACE} ${variant === 'ghost' ? 'px-20' : 'px-28'}`} {...rest}>
          {children}
        </button>
      </NoiseBackground>
    </span>
  )
}

/** A thin arrow for actions (outline only, 1.5px stroke). */
export function ArrowRight({ size = 16 }: { size?: number }) {
  return (
    <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="square">
      <path d="M4 12h15M13 6l6 6-6 6" />
    </svg>
  )
}
