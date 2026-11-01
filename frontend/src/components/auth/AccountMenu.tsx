import { AnimatePresence, motion } from 'motion/react'
import { useEffect, useRef, useState } from 'react'
import { authCopy as copy } from '../../content/auth'
import { useAuth } from '../../hooks/useAuth'
import { formatTokens } from '../../lib/admin'
import { ADMIN_HASH } from '../../lib/hashRoute'

/**
 * The account button in the studio's nav bar: the person's initial, opening a small menu with who is signed in,
 * this month's model tokens against their quota, the admin dashboard (for admins), and sign out.
 *
 * Hidden when the server runs without accounts (then there is nobody to sign out). Closes on Escape or a click
 * outside, and gives focus back to the button.
 */
export function AccountMenu() {
  const { me, signOut, refresh } = useAuth()
  const [open, setOpen] = useState(false)
  // The menu is 280px wide. It normally opens to the LEFT of the button (lined up with its right edge); when the
  // button sits near the left side of the screen (the nav wraps on narrow windows) that would push the menu off
  // screen, so it opens to the right instead. Worked out each time it opens.
  const [alignLeft, setAlignLeft] = useState(false)
  const box = useRef<HTMLDivElement>(null)
  const button = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!open) return
    void refresh() // fresh numbers each time it opens
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false)
        button.current?.focus()
      }
    }
    const onClick = (event: MouseEvent) => {
      if (box.current && !box.current.contains(event.target as Node)) setOpen(false)
    }
    window.addEventListener('keydown', onKey)
    window.addEventListener('mousedown', onClick)
    return () => {
      window.removeEventListener('keydown', onKey)
      window.removeEventListener('mousedown', onClick)
    }
  }, [open, refresh])

  if (!me || !me.auth_enabled) return null
  const { user } = me
  const quota = user.monthly_token_quota
  const share = quota ? Math.min(1, me.tokens_used / quota) : null
  const initial = (user.name || user.email).trim().charAt(0).toUpperCase()

  return (
    <div ref={box} className="relative">
      <button
        ref={button}
        type="button"
        onClick={() => {
          const edge = button.current?.getBoundingClientRect().right ?? Infinity
          setAlignLeft(edge < 300)
          setOpen((value) => !value)
        }}
        aria-expanded={open}
        aria-haspopup="menu"
        aria-label={`${copy.menu}: ${user.email}`}
        className="flex size-40 items-center justify-center rounded-pill border border-line bg-soot text-[15px] font-semibold text-chalk transition-colors hover:border-slate focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-vermilion lg:size-44"
      >
        {initial}
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            role="menu"
            initial={{ opacity: 0, y: -6, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.98 }}
            transition={{ duration: 0.15 }}
            className={`absolute top-[calc(100%+10px)] ${alignLeft ? 'left-0' : 'right-0'} z-40 flex w-[280px] flex-col gap-14 rounded-card border border-line bg-carbon p-16 shadow-[0_20px_60px_-20px_rgba(0,0,0,0.8)]`}
          >
            <div>
              <p className="font-code text-[11px] uppercase tracking-[0.08em] text-smoke">{copy.signedInAs}</p>
              <p className="mt-4 truncate text-[15px] font-medium text-chalk">{user.name || user.email}</p>
              {user.name && <p className="truncate text-[13px] text-smoke">{user.email}</p>}
            </div>
            <div className="flex flex-col gap-6">
              <div className="flex items-baseline justify-between gap-8">
                <span className="font-code text-[11px] uppercase tracking-[0.08em] text-smoke">{copy.tokens}</span>
                <span className="text-[13px] text-chalk">
                  {formatTokens(me.tokens_used)} / {quota ? formatTokens(quota) : copy.noLimit}
                </span>
              </div>
              <div className="h-6 overflow-hidden rounded-pill bg-soot">
                <div
                  className={`h-full rounded-pill ${share === null ? 'w-full bg-slate/40' : share >= 0.9 ? 'bg-vermilion' : share >= 0.7 ? 'bg-[#f0a33a]' : 'bg-[#4fbf7a]'}`}
                  style={share === null ? undefined : { width: `${Math.max(2, share * 100)}%` }}
                />
              </div>
            </div>
            <div className="flex flex-col gap-4 border-t border-line pt-12">
              {user.role === 'admin' && (
                <a role="menuitem" href={ADMIN_HASH} onClick={() => setOpen(false)} className="flex h-40 items-center rounded-control px-10 text-[14px] text-chalk hover:bg-soot focus-visible:outline-2 focus-visible:outline-vermilion">
                  {copy.admin}
                </a>
              )}
              <button role="menuitem" type="button" onClick={() => void signOut()} className="flex h-40 items-center rounded-control px-10 text-left text-[14px] text-chalk hover:bg-soot focus-visible:outline-2 focus-visible:outline-vermilion">
                {copy.signOut}
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
