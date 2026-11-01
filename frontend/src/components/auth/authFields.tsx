import type { ReactNode } from 'react'

/** The look of every text field on the sign-in card. */
export const INPUT =
  'h-48 w-full rounded-[14px] border border-ink/12 bg-white/85 px-14 text-[16px] text-ink shadow-[inset_0_1px_2px_rgba(28,34,44,0.06)] ' +
  'transition-[border-color,box-shadow] placeholder:text-stone/60 focus:border-cobalt/60 focus:outline-none focus:ring-4 focus:ring-cobalt/15'

/** The card's main button (sign in, send link, save). */
export const PRIMARY_BUTTON =
  'group mt-6 flex h-52 items-center justify-center gap-10 rounded-pill bg-cobalt text-[16px] font-strong text-white shadow-[0_10px_30px_-8px_rgba(82,102,235,0.6)] transition-[background-color,transform,opacity] hover:bg-cobalt-deep active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-55 focus-visible:outline-2 focus-visible:outline-offset-3 focus-visible:outline-cobalt'

/** A small text-style button (switching between sign in, create account and forgot password). */
export const LINK_BUTTON =
  'font-strong text-cobalt underline decoration-cobalt/30 underline-offset-4 hover:decoration-cobalt focus-visible:outline-2 focus-visible:outline-cobalt'

export function Field({ id, label, note, children }: { id: string; label: string; note?: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-6">
      <label htmlFor={id} className="text-caption font-strong text-ink">
        {label}
        {note && <span className="ml-6 font-normal text-stone">({note})</span>}
      </label>
      {children}
    </div>
  )
}

/** A mistake (role=alert, read out at once) or good news, inside the card. */
export function CardMessage({ id, tone, children }: { id?: string; tone: 'problem' | 'good'; children: ReactNode }) {
  const look = tone === 'problem' ? 'border-[#e0835f]/40 bg-[#fdeee7] text-[#8a3a1c]' : 'border-moss/30 bg-moss/10 text-ink'
  return (
    <p id={id} role={tone === 'problem' ? 'alert' : 'status'} className={`rounded-[14px] border px-14 py-10 text-caption ${look}`}>
      {children}
    </p>
  )
}
