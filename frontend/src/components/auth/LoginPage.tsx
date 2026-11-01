import { AnimatePresence, motion, useAnimationControls } from 'motion/react'
import { useEffect, useId, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { authCopy as copy } from '../../content/auth'
import { heroMedia } from '../../content/heroMedia'
import { useAuth } from '../../hooks/useAuth'
import { usePrefersReducedMotion } from '../../hooks/usePrefersReducedMotion'
import { ApiError, getConfig } from '../../lib/api/client'
import { LOGIN_HASH, SIGNUP_HASH, STUDIO_HASH, resetTokenFromHash, screenFromHash } from '../../lib/hashRoute'
import { ArchwayWordmark } from '../ui/ArchwayWordmark'
import { CardMessage, Field, INPUT, LINK_BUTTON, PRIMARY_BUTTON } from './authFields'
import { RecoveryPanel, type Recovery } from './RecoveryPanel'

type Mode = 'signIn' | 'signUp'

/** An emailed reset link (#/login/reset/<token>) opens the card on choosing a new password. */
const recoveryFromHash = (hash: string): Recovery | null => {
  const token = resetTokenFromHash(hash)
  return token ? { kind: 'reset', token } : null
}

interface LoginPageProps {
  /** Called once the person is signed in (the app then opens the workspace through the space film). */
  onSignedIn: () => void
}

/** Where the laptop sits in the hero picture (fractions of its width and height): the camera eases in toward it. */
const LAPTOP = { x: 0.505, y: 0.565 }

/**
 * The sign-in page: the welcome page's morning, alive.
 *
 *   the scene   the hero picture of the desk on the misty hill, drifting slowly (a slow "Ken Burns" pan), with
 *               mist banks moving across the valley and the sunrise glow breathing
 *   the card    frosted glass that floats in; a sliding pill switches Sign in / Create account; the headline
 *               arrives word by word; fields glow when focused; a wrong password shakes the card gently
 *   signing in  the camera eases in toward the laptop on the desk, then the space film carries the person into
 *               the studio (onSignedIn)
 *
 * With reduced motion it is the same page, still: no drift, no mist, no zoom.
 */
export function LoginPage({ onSignedIn }: LoginPageProps) {
  const still = usePrefersReducedMotion()
  const auth = useAuth()
  // "Create account" links open the page on that tab (#/login/new); everything else on signing in.
  const [mode, setMode] = useState<Mode>(() => (window.location.hash === SIGNUP_HASH ? 'signUp' : 'signIn'))
  // Forgot password: asking for a link, or choosing a new password with one (RecoveryPanel). null = the normal card.
  const [recovery, setRecovery] = useState<Recovery | null>(() => recoveryFromHash(window.location.hash))
  const [notice, setNotice] = useState<string | null>(null)
  // "Forgot password?" appears only when the server can email a link.
  const [resetByEmail, setResetByEmail] = useState(false)
  useEffect(() => {
    getConfig().then((config) => setResetByEmail(config.password_reset === true)).catch(() => {})
  }, [])
  // The page can already be on screen when a "Create account" or "Sign in" link changes the address (for example
  // after signing out). Follow the address then too, not only when the page first appears.
  useEffect(() => {
    const onHashChange = () => {
      const fromLink = recoveryFromHash(window.location.hash)
      if (fromLink) setRecovery(fromLink)
      else if (window.location.hash === SIGNUP_HASH) setMode('signUp')
      else if (screenFromHash(window.location.hash) === 'login') setMode('signIn')
    }
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [shown, setShown] = useState(false)
  const [busy, setBusy] = useState(false)
  const [problem, setProblem] = useState<string | null>(null)
  const [arriving, setArriving] = useState(false)
  const card = useAnimationControls()
  const emailRef = useRef<HTMLInputElement>(null)
  const ids = { name: useId(), email: useId(), password: useId(), hint: useId(), problem: useId() }

  useEffect(() => {
    emailRef.current?.focus({ preventScroll: true })
  }, [])

  // Already signed in when the page opens (an old bookmark, the Back button): go straight on to the studio.
  const submitting = useRef(false)
  useEffect(() => {
    if (auth.status === 'signedIn' && !submitting.current && screenFromHash(window.location.hash) === 'login' && !recoveryFromHash(window.location.hash)) {
      window.location.replace(STUDIO_HASH)
    }
  }, [auth.status])

  // Signed in: the camera eases toward the laptop, then the film takes over (straight away with reduced motion).
  useEffect(() => {
    if (!arriving || auth.status !== 'signedIn') return
    const timer = window.setTimeout(onSignedIn, still ? 0 : 900)
    return () => window.clearTimeout(timer)
  }, [arriving, auth.status, onSignedIn, still])

  const switchMode = (next: Mode) => {
    setMode(next)
    setProblem(null)
    setNotice(null)
  }

  const endRecovery = (changed: boolean) => {
    // The reset link's token leaves the address bar (replaceState: no new history entry, no hashchange).
    if (resetTokenFromHash(window.location.hash)) window.history.replaceState(null, '', LOGIN_HASH)
    setRecovery(null)
    switchMode('signIn')
    setPassword('')
    setNotice(changed ? copy.recovery.done : null)
  }

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (busy) return
    setBusy(true)
    setProblem(null)
    setNotice(null)
    submitting.current = true
    try {
      if (mode === 'signIn') await auth.signIn(email.trim(), password)
      else await auth.signUp(email.trim(), password, name.trim() || null)
      setArriving(true) // the effect below takes it from here, once the app knows the person is signed in
    } catch (error) {
      submitting.current = false
      // A gateway error (502-504) means the dev server or host is up but Archway's backend is not answering.
      const down = !(error instanceof ApiError) || [502, 503, 504].includes(error.status)
      setProblem(down ? copy.unreachable : error.message)
      if (!still) void card.start({ x: [0, -10, 9, -6, 4, 0], transition: { duration: 0.45 } })
    } finally {
      setBusy(false)
    }
  }

  const passwordOk = password.length >= 10
  const words = copy.headline[mode].split(' ')

  return (
    <div className="relative isolate min-h-dvh overflow-clip bg-dawn text-ink">
      {/* --- The scene ------------------------------------------------------------------------------------- */}
      {/* A fixed layer that CLIPS (never scrolls): the drifting picture, glow and mist reach past the window's edges,
          and a box that merely hides overflow can still be scrolled by the browser when a field takes focus. */}
      <div aria-hidden="true" className="pointer-events-none fixed inset-0 -z-10 overflow-clip">
      <motion.div
        aria-hidden="true"
        className="absolute inset-0 bg-cover bg-center"
        style={{ backgroundImage: `url(${heroMedia.posterSrc})`, transformOrigin: `${LAPTOP.x * 100}% ${LAPTOP.y * 100}%` }}
        initial={still ? false : { scale: 1.12, x: '1.5%' }}
        animate={
          arriving && !still
            ? { scale: 2.6, x: 0, y: 0, transition: { duration: 0.95, ease: [0.6, 0, 0.3, 1] } }
            : still
              ? undefined
              : { scale: [1.12, 1.18, 1.12], x: ['1.5%', '-1.5%', '1.5%'], transition: { duration: 48, repeat: Infinity, ease: 'easeInOut' } }
        }
      />
      {/* The sunrise glow, breathing, and the morning light that keeps the card's side readable. */}
      <motion.div
        aria-hidden="true"
        className="pointer-events-none absolute -left-[10%] -top-[20%] h-[75vh] w-[70vw] rounded-full bg-blush blur-3xl"
        initial={{ opacity: 0.45 }}
        animate={still ? undefined : { opacity: [0.35, 0.6, 0.35] }}
        transition={{ duration: 9, repeat: Infinity, ease: 'easeInOut' }}
      />
      {!still && (
        <div aria-hidden="true" className="pointer-events-none absolute inset-x-0 top-[38%] h-[30%]">
          <span className="login-mist login-mist-a" />
          <span className="login-mist login-mist-b" />
          <span className="login-mist login-mist-c" />
        </div>
      )}
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 bg-linear-to-r from-transparent via-dawn/10 to-dawn/55 max-lg:bg-dawn/35" />
      </div>
      <motion.div
        aria-hidden="true"
        className="pointer-events-none fixed inset-0 z-20 bg-white"
        initial={{ opacity: 0 }}
        animate={{ opacity: arriving && !still ? 0.85 : 0 }}
        transition={{ duration: 0.9, ease: 'easeIn' }}
      />

      {/* --- The page ---------------------------------------------------------------------------------------- */}
      <div className="relative flex min-h-dvh flex-col px-16 py-20 md:px-40 md:py-32">
        <header className="flex items-center justify-between gap-16">
          <a href="#" aria-label={copy.back} className="w-[150px] drop-shadow-[0_2px_12px_rgba(0,0,0,0.25)] focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-cobalt md:w-[190px]">
            <ArchwayWordmark />
          </a>
          <a href="#" className="rounded-pill bg-white/65 px-16 py-8 text-caption font-strong text-ink backdrop-blur-md transition-colors hover:bg-white focus-visible:outline-2 focus-visible:outline-cobalt">
            ← {copy.back}
          </a>
        </header>

        <main className="flex flex-1 items-center justify-center py-32 lg:justify-end lg:pr-[4vw]">
          {/* The outer layer floats the card in (and away when signing in); the inner one shakes on a mistake. */}
          <motion.div
            className="w-full max-w-[440px]"
            initial={still ? false : { opacity: 0, y: 36, filter: 'blur(8px)' }}
            animate={{ opacity: arriving && !still ? 0 : 1, y: arriving && !still ? -24 : 0, filter: 'blur(0px)' }}
            transition={{ type: 'spring', stiffness: 120, damping: 18, delay: arriving ? 0 : 0.15 }}
          >
          <motion.section
            aria-labelledby="login-headline"
            animate={card}
            className="w-full rounded-[28px] border border-white/70 bg-white/72 p-24 shadow-lift backdrop-blur-xl md:p-32"
          >
            {recovery ? (
              <RecoveryPanel recovery={recovery} initialEmail={email} onDone={endRecovery} />
            ) : (
            <>
            {/* Sign in / Create account: a pill slides to the chosen side */}
            <div role="tablist" aria-label={`${copy.tabs.signIn} / ${copy.tabs.signUp}`} className="relative grid grid-cols-2 rounded-pill bg-ink/[0.06] p-4">
              {(['signIn', 'signUp'] as Mode[]).map((option) => (
                <button
                  key={option}
                  type="button"
                  role="tab"
                  aria-selected={mode === option}
                  onClick={() => switchMode(option)}
                  className="relative z-10 h-40 rounded-pill text-[14px] font-strong transition-colors focus-visible:outline-2 focus-visible:outline-cobalt"
                >
                  {mode === option && (
                    <motion.span
                      layoutId="login-tab"
                      className="absolute inset-0 -z-10 rounded-pill bg-white shadow-[0_2px_10px_rgba(28,34,44,0.12)]"
                      transition={still ? { duration: 0 } : { type: 'spring', stiffness: 380, damping: 32 }}
                    />
                  )}
                  <span className={mode === option ? 'text-ink' : 'text-stone'}>{copy.tabs[option]}</span>
                </button>
              ))}
            </div>

            {/* The headline arrives word by word, again whenever the tab changes */}
            <AnimatePresence mode="wait" initial={false}>
              <motion.div key={mode} className="mt-28" exit={still ? undefined : { opacity: 0, y: -8, transition: { duration: 0.15 } }}>
                <h1 id="login-headline" className="font-display text-[clamp(30px,4vw,40px)] leading-[1.05] font-strong tracking-[-0.03em] text-ink">
                  {words.map((word, index) => (
                    <motion.span
                      key={`${word}-${index}`}
                      className="mr-[0.25em] inline-block"
                      initial={still ? false : { opacity: 0, y: 18, rotateX: 50 }}
                      animate={{ opacity: 1, y: 0, rotateX: 0 }}
                      transition={{ delay: 0.25 + index * 0.08, type: 'spring', stiffness: 220, damping: 20 }}
                    >
                      {word}
                    </motion.span>
                  ))}
                </h1>
                <motion.p
                  className="mt-10 text-body text-stone"
                  initial={still ? false : { opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 0.45 }}
                >
                  {copy.lead[mode]}
                </motion.p>
              </motion.div>
            </AnimatePresence>

            <form className="mt-24 flex flex-col gap-14" onSubmit={(event) => void submit(event)} noValidate>
              <AnimatePresence initial={false}>
                {mode === 'signUp' && (
                  <motion.div
                    key="name"
                    initial={still ? false : { height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={still ? undefined : { height: 0, opacity: 0 }}
                    className="overflow-hidden"
                  >
                    <Field id={ids.name} label={copy.name} note={copy.nameOptional}>
                      <input id={ids.name} value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" maxLength={80} className={INPUT} />
                    </Field>
                  </motion.div>
                )}
              </AnimatePresence>

              <Field id={ids.email} label={copy.email}>
                <input
                  ref={emailRef} id={ids.email} type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
                  autoComplete="email" inputMode="email" maxLength={254} aria-describedby={problem ? ids.problem : undefined} className={INPUT}
                />
              </Field>

              <Field id={ids.password} label={copy.password}>
                <div className="relative">
                  <input
                    id={ids.password} type={shown ? 'text' : 'password'} required value={password} onChange={(e) => setPassword(e.target.value)}
                    autoComplete={mode === 'signIn' ? 'current-password' : 'new-password'} maxLength={200}
                    aria-describedby={mode === 'signUp' ? ids.hint : undefined} className={`${INPUT} pr-72`}
                  />
                  <button
                    type="button" onClick={() => setShown((value) => !value)} aria-pressed={shown}
                    className="absolute top-1/2 right-6 h-36 -translate-y-1/2 rounded-pill px-12 text-caption font-strong text-stone hover:bg-ink/5 hover:text-ink focus-visible:outline-2 focus-visible:outline-cobalt"
                  >
                    {shown ? copy.hide : copy.show}
                  </button>
                </div>
                {mode === 'signIn' && resetByEmail && (
                  <button type="button" onClick={() => setRecovery({ kind: 'forgot' })} className={`mt-8 self-end text-caption ${LINK_BUTTON}`}>
                    {copy.forgot}
                  </button>
                )}
                {mode === 'signUp' && (
                  <p id={ids.hint} className={`mt-6 flex items-center gap-6 text-caption transition-colors ${passwordOk ? 'text-moss' : 'text-stone'}`}>
                    <span aria-hidden="true">{passwordOk ? '✓' : '·'}</span>
                    {copy.passwordHint}
                  </p>
                )}
              </Field>

              {notice && <CardMessage tone="good">{notice}</CardMessage>}

              <AnimatePresence>
                {problem && (
                  <motion.p
                    id={ids.problem} role="alert"
                    initial={still ? false : { opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                    className="rounded-[14px] border border-[#e0835f]/40 bg-[#fdeee7] px-14 py-10 text-caption text-[#8a3a1c]"
                  >
                    {problem}
                  </motion.p>
                )}
              </AnimatePresence>

              <button
                type="submit"
                disabled={busy || arriving || !email.trim() || !password || (mode === 'signUp' && !passwordOk)}
                className={PRIMARY_BUTTON}
              >
                {busy || arriving ? (
                  <>
                    <span aria-hidden="true" className="size-16 animate-spin rounded-full border-2 border-white/40 border-t-white" />
                    {copy.working[mode]}
                  </>
                ) : (
                  <>
                    {copy.submit[mode]}
                    <span aria-hidden="true" className="transition-transform group-hover:translate-x-4">→</span>
                  </>
                )}
              </button>
            </form>

            <p className="mt-20 text-center text-caption text-stone">
              {copy.switchTo[mode]}{' '}
              <button
                type="button" onClick={() => switchMode(mode === 'signIn' ? 'signUp' : 'signIn')}
                className={LINK_BUTTON}
              >
                {copy.switchAction[mode]}
              </button>
            </p>
            </>
            )}
            <p className="mt-16 border-t border-ink/10 pt-14 text-center text-[12px] leading-[1.5] text-stone">{copy.privacy}</p>
          </motion.section>
          </motion.div>
        </main>
      </div>
    </div>
  )
}
