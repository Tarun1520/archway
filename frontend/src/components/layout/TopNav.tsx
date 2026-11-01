import { authCopy } from '../../content/auth'
import { navLinks } from '../../content/welcome'
import { useAuth } from '../../hooks/useAuth'
import { useGoToWorkspace } from '../../hooks/useGoToWorkspace'
import { useScrolledPast } from '../../hooks/useScrolledPast'
import { LOGIN_HASH, SIGNUP_HASH } from '../../lib/hashRoute'
import { BrandMark } from '../ui/BrandMark'

/**
 * The bar fixed to the top of the page.
 *
 * Over the hero it is fully transparent so the picture shows through. Once the
 * page has scrolled a little, it turns into frosted glass (a see-through dark
 * fill with the content behind it blurred) so the links stay readable.
 *
 * On the right, always visible: "Sign in" and "Create account" while signed out
 * (they open the sign-in page, and also show when the backend cannot be
 * reached), or "Open studio" once signed in (through the space film). While the
 * app is still asking who is signed in (a moment), nothing shows, so the
 * buttons never flicker from one to the other.
 */
export function TopNav() {
  const scrolled = useScrolledPast(24)
  const { status, me, signOut } = useAuth()
  const goToWorkspace = useGoToWorkspace()

  const surface = scrolled
    ? 'border-mist/10 bg-onyx/70 backdrop-blur-[20px]'
    : 'border-transparent bg-transparent'

  return (
    <header className={`fixed inset-x-0 top-0 z-50 border-b transition-colors duration-300 ${surface}`}>
      <nav aria-label="Main" className="mx-auto flex h-64 max-w-page items-center justify-between gap-16 px-20 md:px-32">
        {/* At the very top the hero shows the name in large letters, so this small one stays hidden until the page scrolls. */}
        <a
          href="#top"
          className={`-ml-8 flex h-44 items-center gap-8 rounded-pill px-8 text-ivory transition-opacity duration-300 ${scrolled ? 'opacity-100' : 'pointer-events-none opacity-0'}`}
          tabIndex={scrolled ? undefined : -1}
          aria-hidden={scrolled ? undefined : true}
        >
          <BrandMark />
          <span className="text-body font-strong tracking-[0.22em] uppercase">Archway</span>
        </a>

        {/* Section links are hidden on small screens, where the page is short enough to scroll. */}
        <ul className="hidden items-center gap-4 lg:ml-auto lg:flex">
          {navLinks.map((link) => (
            <li key={link.href}>
              <a
                href={link.href}
                className="inline-flex h-36 items-center rounded-pill px-16 text-body text-ivory transition-colors duration-200 hover:bg-ivory/10"
              >
                {link.label}
              </a>
            </li>
          ))}
        </ul>

        {/* Signing in, always in reach */}
        <div className="flex items-center gap-8">
          {/* Offered whenever it is not certain someone is signed in: signed out, or the backend cannot be reached. */}
          {(status === 'signedOut' || status === 'unreachable') && (
            <>
              <a
                href={LOGIN_HASH}
                className="inline-flex h-40 items-center rounded-pill px-16 text-body font-strong text-ivory transition-colors duration-200 hover:bg-ivory/10 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ivory"
              >
                {authCopy.tabs.signIn}
              </a>
              <a
                href={SIGNUP_HASH}
                className="hidden h-40 items-center rounded-pill bg-ivory px-18 text-body font-strong text-onyx transition-transform duration-200 hover:scale-[1.03] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ivory sm:inline-flex"
              >
                {authCopy.tabs.signUp}
              </a>
            </>
          )}
          {status === 'signedIn' && me && (
            // Signed in: a quiet "Sign out" beside the main button, so leaving is always one click away.
            <button
              type="button"
              onClick={() => void signOut()}
              title={me.user.email}
              className="inline-flex h-40 items-center rounded-pill px-16 text-body font-strong text-ivory transition-colors duration-200 hover:bg-ivory/10 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ivory"
            >
              {authCopy.signOut}
            </button>
          )}
          {status === 'signedIn' && me && (
            <button
              type="button"
              onClick={goToWorkspace}
              title={me?.user.email}
              className="inline-flex h-40 items-center gap-8 rounded-pill bg-ivory px-18 text-body font-strong text-onyx transition-transform duration-200 hover:scale-[1.03] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ivory"
            >
              {authCopy.openStudio}
              <span aria-hidden="true">→</span>
            </button>
          )}
        </div>
      </nav>
    </header>
  )
}
