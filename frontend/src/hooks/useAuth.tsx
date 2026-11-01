import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { ApiError, getMe, SIGNED_OUT_EVENT, signIn as apiSignIn, signOut as apiSignOut, signUp as apiSignUp } from '../lib/api/client'
import type { Me } from '../lib/api/types'

/**
 * Who is signed in, for the whole app.
 *
 *   status   'loading' until the backend has answered; then 'signedIn' or 'signedOut'; or 'unreachable' when the
 *            backend cannot be reached at all (it is asked again every few seconds, so the page recovers on its own)
 *   me       the account and what is left of its monthly quota (null when signed out)
 *   signIn / signUp / signOut / refresh
 *
 * The session itself is a cookie the page cannot read (HttpOnly): this only asks the backend "who am I?". When any
 * request comes back 401 (the session expired, or the admin blocked the account), the API client raises an event and
 * this switches to 'signedOut', so the sign-in page appears instead of a broken screen.
 *
 * When the backend runs without accounts (AUTH_ENABLED=false), "who am I" answers with the local admin, so nothing
 * here ever asks anyone to sign in.
 */
type Status = 'loading' | 'signedIn' | 'signedOut' | 'unreachable'

/** How often to ask again while the backend cannot be reached. */
const RETRY_MS = 5000

interface AuthValue {
  status: Status
  me: Me | null
  signIn: (email: string, password: string) => Promise<void>
  signUp: (email: string, password: string, name: string | null) => Promise<void>
  signOut: () => Promise<void>
  refresh: () => Promise<void>
}

const AuthContext = createContext<AuthValue>({
  status: 'loading', me: null,
  signIn: async () => {}, signUp: async () => {}, signOut: async () => {}, refresh: async () => {},
})

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Status>('loading')
  const [me, setMe] = useState<Me | null>(null)

  const refresh = useCallback(async () => {
    try {
      setMe(await getMe())
      setStatus('signedIn')
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        setMe(null)
        setStatus('signedOut')
      } else {
        // The backend cannot be reached (stopped, restarting, offline). That is NOT "signed in": the welcome page
        // still offers Sign in, and the studio shows its own "cannot reach the backend" notice.
        setMe(null)
        setStatus('unreachable')
      }
    }
  }, [])

  // While the backend cannot be reached, keep asking, so the page recovers by itself once it is back.
  useEffect(() => {
    if (status !== 'unreachable') return
    const timer = window.setInterval(() => void refresh(), RETRY_MS)
    return () => window.clearInterval(timer)
  }, [status, refresh])

  useEffect(() => {
    void refresh()
    const onSignedOut = () => {
      setMe(null)
      setStatus('signedOut')
    }
    window.addEventListener(SIGNED_OUT_EVENT, onSignedOut)
    return () => window.removeEventListener(SIGNED_OUT_EVENT, onSignedOut)
  }, [refresh])

  const value = useMemo<AuthValue>(() => ({
    status, me, refresh,
    signIn: async (email, password) => {
      setMe(await apiSignIn(email, password))
      setStatus('signedIn')
    },
    signUp: async (email, password, name) => {
      setMe(await apiSignUp(email, password, name))
      setStatus('signedIn')
    },
    signOut: async () => {
      await apiSignOut()
      setMe(null)
      setStatus('signedOut')
    },
  }), [status, me, refresh])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthValue {
  return useContext(AuthContext)
}
