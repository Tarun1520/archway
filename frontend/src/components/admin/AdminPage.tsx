import { AnimatePresence, motion } from 'motion/react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { adminCopy as copy } from '../../content/admin'
import { useAuth } from '../../hooks/useAuth'
import { ApiError, changeUser, listUsers } from '../../lib/api/client'
import type { UserChange, UserUsage } from '../../lib/api/types'
import { formatTokens, quotaShare, sinceText } from '../../lib/admin'

/** How often the dashboard asks for fresh numbers while it is on screen. */
const REFRESH_MS = 3000

/**
 * The admin dashboard (#/admin): every account, its live usage this month, and the controls.
 *
 *   live       the numbers are asked for again every 3 seconds while the page is visible (paused in a hidden tab);
 *              an account whose run is working right now has a pulsing dot
 *   per user   model tokens used against the monthly quota (a bar that turns amber, then red, as it fills),
 *              model, decision-model and GitHub calls, runs started this month, projects, last seen
 *   controls   set the monthly token quota (presets or an exact number; "No limit"), block or unblock (blocking signs
 *              the person out everywhere), make admin or remove admin. The backend refuses anything that would lock
 *              every admin out.
 *
 * Only usage counts are shown here, never anyone's ideas or projects.
 */
export function AdminPage() {
  const { me, signOut } = useAuth()
  const [rows, setRows] = useState<UserUsage[] | null>(null)
  const [problem, setProblem] = useState<string | null>(null)
  const [updated, setUpdated] = useState<number | null>(null)
  const [query, setQuery] = useState('')
  const [, tick] = useState(0)

  const load = useCallback(async () => {
    try {
      setRows(await listUsers())
      setUpdated(Date.now())
      setProblem(null)
    } catch (error) {
      setProblem(error instanceof ApiError ? error.message : copy.unreachable)
    }
  }, [])

  useEffect(() => {
    if (me?.user.role !== 'admin') return
    void load()
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') void load()
      tick((n) => n + 1) // keeps "updated 2s ago" current
    }, REFRESH_MS)
    return () => window.clearInterval(timer)
  }, [load, me?.user.role])

  const change = async (userId: string, body: UserChange) => {
    try {
      const row = await changeUser(userId, body)
      setRows((now) => now?.map((item) => (item.user.id === userId ? row : item)) ?? null)
      setProblem(null)
    } catch (error) {
      setProblem(error instanceof ApiError ? error.message : copy.unreachable)
    }
  }

  const shown = useMemo(() => {
    const term = query.trim().toLowerCase()
    return (rows ?? []).filter((row) => !term || row.user.email.includes(term) || (row.user.name ?? '').toLowerCase().includes(term))
  }, [rows, query])
  const totals = useMemo(() => ({
    accounts: rows?.length ?? 0,
    working: rows?.filter((row) => row.working).length ?? 0,
    tokens: rows?.reduce((sum, row) => sum + row.tokens, 0) ?? 0,
    runs: rows?.reduce((sum, row) => sum + row.runs, 0) ?? 0,
  }), [rows])

  if (me?.user.role !== 'admin') {
    return (
      <div className="studio-theme flex min-h-dvh flex-col items-center justify-center gap-16 bg-void p-24 text-center">
        <p className="text-h3 font-bold text-chalk">{copy.notAdmin}</p>
        <a href="#/studio" className="text-[15px] text-smoke underline underline-offset-4 hover:text-chalk">{copy.backToStudio}</a>
      </div>
    )
  }

  return (
    <div className="studio-theme min-h-dvh bg-void p-12 md:p-16">
      <header className="sticky top-12 z-20 flex flex-wrap items-center gap-x-16 gap-y-10 rounded-card border border-line bg-carbon/85 px-16 py-10 backdrop-blur-md md:top-16 md:px-20">
        <a href="#/studio" className="text-[18px] font-bold tracking-[-0.03em] text-chalk">Archway</a>
        <span className="rounded-pill border border-vermilion/50 px-10 py-2 font-code text-[11px] uppercase tracking-[0.08em] text-vermilion">{copy.badge}</span>
        <p className="ml-auto flex items-center gap-8 font-code text-label uppercase text-smoke" aria-live="off">
          <span aria-hidden="true" className="live-dot inline-block size-8 rounded-pill bg-vermilion" />
          {copy.live} · {updated ? sinceText(updated) : '…'}
        </p>
        <a href="#/studio" className="flex h-40 items-center rounded-pill border border-line px-16 text-[14px] text-chalk hover:bg-soot">{copy.backToStudio}</a>
        <button type="button" onClick={() => void signOut()} className="flex h-40 items-center rounded-pill bg-chalk px-16 text-[14px] font-semibold text-void hover:scale-[1.03]">
          {copy.signOut}
        </button>
      </header>

      <main className="mx-auto mt-32 flex max-w-[1200px] flex-col gap-32 px-4 md:mt-48">
        <div>
          <h1 className="text-h2 font-bold tracking-[-0.03em] text-chalk md:text-h1">{copy.title}</h1>
          <p className="mt-12 max-w-2xl text-lead text-smoke">{copy.lead}</p>
        </div>

        <div className="grid grid-cols-2 gap-12 md:grid-cols-4">
          <Stat label={copy.stats.accounts} value={String(totals.accounts)} />
          <Stat label={copy.stats.working} value={String(totals.working)} live={totals.working > 0} />
          <Stat label={copy.stats.tokens} value={formatTokens(totals.tokens)} />
          <Stat label={copy.stats.runs} value={String(totals.runs)} />
        </div>

        {problem && <p role="alert" className="border-l-2 border-vermilion py-4 pl-12 text-[15px] text-chalk">{problem}</p>}

        <div className="flex flex-wrap items-center justify-between gap-12">
          <h2 className="font-code text-label uppercase text-smoke">{copy.accounts}</h2>
          <input
            type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder={copy.search} aria-label={copy.search}
            className="h-40 w-full max-w-[280px] rounded-pill border border-line bg-soot px-16 text-[14px] text-chalk placeholder:text-smoke focus:border-slate focus:outline-none"
          />
        </div>

        {rows === null ? (
          <p className="text-[15px] text-smoke">{copy.loading}</p>
        ) : (
          <ul className="flex flex-col gap-12">
            <AnimatePresence initial={false}>
              {shown.map((row) => (
                <motion.li key={row.user.id} layout initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
                  <UserRow row={row} isMe={row.user.id === me.user.id} onChange={(body) => change(row.user.id, body)} />
                </motion.li>
              ))}
            </AnimatePresence>
            {shown.length === 0 && <li className="text-[15px] text-smoke">{copy.noMatch}</li>}
          </ul>
        )}
        <p className="pb-48 text-[13px] text-smoke">{copy.footnote}</p>
      </main>
    </div>
  )
}

function Stat({ label, value, live = false }: { label: string; value: string; live?: boolean }) {
  return (
    <div className="flex flex-col gap-6 rounded-card border border-line bg-carbon/70 p-16">
      <span className="flex items-center gap-8 font-code text-[11px] uppercase tracking-[0.08em] text-smoke">
        {live && <span aria-hidden="true" className="live-dot inline-block size-6 rounded-pill bg-vermilion" />}
        {label}
      </span>
      <motion.span key={value} initial={{ opacity: 0.4 }} animate={{ opacity: 1 }} className="text-[28px] font-bold tracking-[-0.02em] text-chalk">
        {value}
      </motion.span>
    </div>
  )
}

const PRESETS = [500_000, 1_000_000, 2_000_000, 5_000_000]

function UserRow({ row, isMe, onChange }: { row: UserUsage; isMe: boolean; onChange: (body: UserChange) => Promise<void> }) {
  const { user } = row
  const share = quotaShare(row)
  const [editing, setEditing] = useState(false)
  const [amount, setAmount] = useState(String(user.monthly_token_quota ?? ''))
  const [confirmBlock, setConfirmBlock] = useState(false)
  const blocked = user.status === 'blocked'
  const barColour = share === null ? 'bg-slate' : share >= 0.9 ? 'bg-vermilion' : share >= 0.7 ? 'bg-[#f0a33a]' : 'bg-[#4fbf7a]'

  const saveQuota = async (value: number) => {
    await onChange({ monthly_token_quota: value })
    setEditing(false)
  }

  return (
    <article className={`flex flex-col gap-16 rounded-card border bg-carbon/70 p-16 md:p-20 ${blocked ? 'border-line opacity-70' : 'border-line'}`}>
      <div className="flex flex-wrap items-start justify-between gap-12">
        <div className="flex min-w-0 flex-col gap-4">
          <p className="flex flex-wrap items-center gap-8 text-[17px] font-semibold text-chalk">
            {row.working && <span title={copy.workingNow} className="live-dot inline-block size-8 rounded-pill bg-vermilion" />}
            <span className="truncate">{user.name || user.email}</span>
            {user.role === 'admin' && <Tag tone="accent">{copy.roles.admin}</Tag>}
            {blocked && <Tag tone="muted">{copy.blocked}</Tag>}
            {isMe && <Tag tone="muted">{copy.you}</Tag>}
          </p>
          <p className="truncate font-code text-[12px] text-smoke">
            {user.name ? `${user.email} · ` : ''}{copy.lastSeen} {user.last_seen_at ? sinceText(Date.parse(user.last_seen_at)) : copy.never}
          </p>
        </div>
        <div className="flex flex-wrap gap-8">
          {!isMe && (
            confirmBlock ? (
              <>
                <SmallButton tone="danger" onClick={() => { setConfirmBlock(false); void onChange({ status: 'blocked' }) }}>{copy.confirmBlock}</SmallButton>
                <SmallButton onClick={() => setConfirmBlock(false)}>{copy.cancel}</SmallButton>
              </>
            ) : blocked ? (
              <SmallButton onClick={() => void onChange({ status: 'active' })}>{copy.unblock}</SmallButton>
            ) : (
              <SmallButton onClick={() => setConfirmBlock(true)}>{copy.block}</SmallButton>
            )
          )}
          {!isMe && (
            <SmallButton onClick={() => void onChange({ role: user.role === 'admin' ? 'user' : 'admin' })}>
              {user.role === 'admin' ? copy.removeAdmin : copy.makeAdmin}
            </SmallButton>
          )}
        </div>
      </div>

      {/* Tokens against the quota */}
      <div className="flex flex-col gap-8">
        <div className="flex flex-wrap items-baseline justify-between gap-8">
          <span className="font-code text-[12px] uppercase tracking-[0.06em] text-smoke">{copy.tokens}</span>
          <span className="text-[15px] text-chalk">
            <strong className="font-semibold">{formatTokens(row.tokens)}</strong>
            <span className="text-smoke"> / {user.monthly_token_quota ? formatTokens(user.monthly_token_quota) : copy.noLimit}</span>
            {share !== null && <span className="ml-8 font-code text-[12px] text-smoke">{Math.round(share * 100)}%</span>}
          </span>
        </div>
        <div className="h-8 overflow-hidden rounded-pill bg-soot" role="meter" aria-label={copy.tokens}
          aria-valuemin={0} aria-valuemax={user.monthly_token_quota ?? undefined} aria-valuenow={row.tokens}>
          <motion.div
            className={`h-full rounded-pill ${barColour}`}
            initial={false}
            animate={{ width: share === null ? '100%' : `${Math.max(1.5, Math.min(100, share * 100))}%`, opacity: share === null ? 0.25 : 1 }}
            transition={{ type: 'spring', stiffness: 90, damping: 20 }}
          />
        </div>
        {editing ? (
          <div className="flex flex-wrap items-center gap-8">
            {PRESETS.map((preset) => (
              <SmallButton key={preset} onClick={() => void saveQuota(preset)}>{formatTokens(preset)}</SmallButton>
            ))}
            <SmallButton onClick={() => void saveQuota(0)}>{copy.noLimit}</SmallButton>
            <form className="flex items-center gap-8" onSubmit={(event) => { event.preventDefault(); const value = Number(amount); if (Number.isFinite(value) && value >= 0) void saveQuota(Math.round(value)) }}>
              <input
                type="number" min={0} step={10000} value={amount} onChange={(event) => setAmount(event.target.value)} aria-label={copy.exactQuota}
                className="h-36 w-[140px] rounded-pill border border-line bg-soot px-12 text-[14px] text-chalk focus:border-slate focus:outline-none"
              />
              <SmallButton tone="primary" type="submit">{copy.save}</SmallButton>
            </form>
            <SmallButton onClick={() => setEditing(false)}>{copy.cancel}</SmallButton>
          </div>
        ) : (
          <div>
            <SmallButton onClick={() => { setAmount(String(user.monthly_token_quota ?? '')); setEditing(true) }}>{copy.setQuota}</SmallButton>
          </div>
        )}
      </div>

      {/* The other counts this month */}
      <dl className="grid grid-cols-2 gap-x-16 gap-y-8 sm:grid-cols-5">
        {[
          [copy.counts.llm, row.llm_calls], [copy.counts.decisions, row.decision_calls], [copy.counts.github, row.github_calls],
          [copy.counts.runs, row.runs], [copy.counts.projects, row.projects],
        ].map(([label, value]) => (
          <div key={label as string} className="flex flex-col gap-2">
            <dt className="font-code text-[11px] uppercase tracking-[0.06em] text-smoke">{label}</dt>
            <dd className="text-[17px] font-semibold text-chalk">{value}</dd>
          </div>
        ))}
      </dl>
    </article>
  )
}

function Tag({ tone, children }: { tone: 'accent' | 'muted'; children: ReactNode }) {
  return (
    <span className={`inline-flex h-22 items-center rounded-pill border px-8 font-code text-[11px] uppercase tracking-[0.06em] ${tone === 'accent' ? 'border-vermilion/50 text-vermilion' : 'border-line text-smoke'}`}>
      {children}
    </span>
  )
}

function SmallButton({ tone = 'plain', type = 'button', onClick, children }: { tone?: 'plain' | 'primary' | 'danger'; type?: 'button' | 'submit'; onClick?: () => void; children: ReactNode }) {
  const look = tone === 'primary' ? 'bg-chalk text-void font-semibold' : tone === 'danger' ? 'border border-vermilion/70 text-vermilion hover:bg-vermilion/10' : 'border border-line text-chalk hover:bg-soot'
  return (
    <button type={type} onClick={onClick} className={`h-36 rounded-pill px-14 text-[13px] transition-colors focus-visible:outline-2 focus-visible:outline-vermilion ${look}`}>
      {children}
    </button>
  )
}
