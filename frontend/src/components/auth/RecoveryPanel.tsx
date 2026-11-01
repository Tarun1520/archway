import { useEffect, useId, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { authCopy } from '../../content/auth'
import { ApiError, requestPasswordReset, resetPassword } from '../../lib/api/client'
import { CardMessage, Field, INPUT, LINK_BUTTON, PRIMARY_BUTTON } from './authFields'

const copy = authCopy.recovery

/** What the panel is doing: asking for a link by email, or choosing a new password with one. */
export type Recovery = { kind: 'forgot' } | { kind: 'reset'; token: string }

interface RecoveryPanelProps {
  recovery: Recovery
  /** The email typed on the sign-in form, so it need not be typed twice. */
  initialEmail: string
  /** Back to signing in; `changed` is true once a new password has been saved. */
  onDone: (changed: boolean) => void
}

/**
 * "Forgot password?" on the sign-in card.
 *
 *   forgot   the email of the account -> the server emails a one-time link. The answer is the same whether or not
 *            the email has an account, so the page says "if an account exists" (it cannot know either).
 *   reset    opened from that link (#/login/reset/<token>): a new password, then back to signing in.
 */
export function RecoveryPanel({ recovery, initialEmail, onDone }: RecoveryPanelProps) {
  const [email, setEmail] = useState(initialEmail)
  const [password, setPassword] = useState('')
  const [shown, setShown] = useState(false)
  const [busy, setBusy] = useState(false)
  const [sent, setSent] = useState(false)
  const [problem, setProblem] = useState<string | null>(null)
  const firstField = useRef<HTMLInputElement>(null)
  const ids = { email: useId(), password: useId(), problem: useId() }
  const forgot = recovery.kind === 'forgot'

  useEffect(() => {
    firstField.current?.focus({ preventScroll: true })
  }, [recovery.kind])

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (busy) return
    setBusy(true)
    setProblem(null)
    try {
      if (recovery.kind === 'forgot') {
        await requestPasswordReset(email.trim())
        setSent(true)
      } else {
        await resetPassword(recovery.token, password)
        onDone(true)
      }
    } catch (error) {
      const down = !(error instanceof ApiError) || [502, 504].includes(error.status)
      setProblem(down ? authCopy.unreachable : error.message)
    } finally {
      setBusy(false)
    }
  }

  const passwordOk = password.length >= 10
  const ready = forgot ? email.trim().length > 2 && !sent : passwordOk

  return (
    <div>
      <h1 id="login-headline" className="font-display text-[clamp(30px,4vw,40px)] leading-[1.05] font-strong tracking-[-0.03em] text-ink">
        {forgot ? copy.forgotHeadline : copy.resetHeadline}
      </h1>
      <p className="mt-10 text-body text-stone">{forgot ? copy.forgotLead : copy.resetLead}</p>

      <form className="mt-24 flex flex-col gap-14" onSubmit={(event) => void submit(event)} noValidate>
        {forgot ? (
          <Field id={ids.email} label={authCopy.email}>
            <input
              ref={firstField} id={ids.email} type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
              autoComplete="email" inputMode="email" maxLength={254} disabled={sent} className={INPUT}
            />
          </Field>
        ) : (
          <Field id={ids.password} label={copy.newPassword}>
            <div className="relative">
              <input
                ref={firstField} id={ids.password} type={shown ? 'text' : 'password'} required value={password}
                onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" maxLength={200} className={`${INPUT} pr-72`}
              />
              <button
                type="button" onClick={() => setShown((value) => !value)} aria-pressed={shown}
                className="absolute top-1/2 right-6 h-36 -translate-y-1/2 rounded-pill px-12 text-caption font-strong text-stone hover:bg-ink/5 hover:text-ink focus-visible:outline-2 focus-visible:outline-cobalt"
              >
                {shown ? authCopy.hide : authCopy.show}
              </button>
            </div>
            <p className={`mt-6 flex items-center gap-6 text-caption transition-colors ${passwordOk ? 'text-moss' : 'text-stone'}`}>
              <span aria-hidden="true">{passwordOk ? '✓' : '·'}</span>
              {authCopy.passwordHint}
            </p>
          </Field>
        )}

        {sent && <CardMessage tone="good">{copy.sent}</CardMessage>}
        {problem && <CardMessage id={ids.problem} tone="problem">{problem}</CardMessage>}

        {!sent && (
          <button type="submit" disabled={busy || !ready} className={PRIMARY_BUTTON}>
            {busy && <span aria-hidden="true" className="size-16 animate-spin rounded-full border-2 border-white/40 border-t-white" />}
            {busy ? (forgot ? copy.sending : copy.saving) : forgot ? copy.send : copy.save}
          </button>
        )}
      </form>

      <p className="mt-20 text-center text-caption text-stone">
        <button type="button" onClick={() => onDone(false)} className={LINK_BUTTON}>
          ← {copy.back}
        </button>
      </p>
    </div>
  )
}
