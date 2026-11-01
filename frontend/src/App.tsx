import { AdminPage } from './components/admin/AdminPage'
import { LoginPage } from './components/auth/LoginPage'
import { SpaceTransition } from './components/transition/SpaceTransition'
import { AuthProvider, useAuth } from './hooks/useAuth'
import { useGoToWorkspace } from './hooks/useGoToWorkspace'
import { useHashRoute } from './hooks/useHashRoute'
import type { Screen } from './lib/hashRoute'
import { StudioPage } from './views/StudioPage'
import { WelcomePage } from './views/WelcomePage'

/**
 * The root component. It chooses between the app's four screens:
 *
 *   the welcome page       the address ends in "/" (or an in-page link)
 *   signing in             "#/login"
 *   the studio workspace   "#/studio"   (signed in only)
 *   the admin dashboard    "#/admin"    (admins only)
 *
 * See lib/hashRoute.ts for how the address is read. Who is signed in comes from AuthProvider (hooks/useAuth.tsx).
 * Opening the studio or the admin dashboard while signed out shows the sign-in page in their place.
 *
 * Going from the welcome page (or the sign-in page) into the workspace plays a short space film first
 * (SpaceTransition), which wraps every screen so it stays on top while the screen changes.
 */
export function App() {
  const screen = useHashRoute()
  return (
    <AuthProvider>
      <SpaceTransition screen={screen}>
        <Screens screen={screen} />
      </SpaceTransition>
    </AuthProvider>
  )
}

function Screens({ screen }: { screen: Screen }) {
  const auth = useAuth()
  const goToWorkspace = useGoToWorkspace()

  if (screen === 'welcome') return <WelcomePage />
  if (auth.status === 'loading') return <div className="min-h-dvh bg-void" aria-busy="true" />
  if (screen === 'login') return <LoginPage onSignedIn={goToWorkspace} />
  // Signed out on a page that needs an account: sign in right here, then the page appears.
  if (auth.status === 'signedOut') return <LoginPage onSignedIn={() => {}} />
  if (screen === 'admin') return <AdminPage />
  return <StudioPage />
}
