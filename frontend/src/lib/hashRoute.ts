/**
 * Which screen to show, decided by the part of the address after "#".
 *
 *   .../            -> the welcome page
 *   .../#/login     -> signing in (#/login/new: opened on creating an account;
 *                      #/login/reset/<token>: choosing a new password from an emailed link)
 *   .../#/studio    -> the studio workspace
 *   .../#/admin     -> the admin dashboard
 *
 * The welcome page also uses "#" for jumps inside the page (like
 * "#how-it-works"). Those do not start with "#/", so they stay on the
 * welcome page.
 *
 * This is a small hand-written router. With only four screens it is easier to
 * read than adding a routing library.
 */

export type Screen = 'welcome' | 'login' | 'studio' | 'admin'

export const STUDIO_HASH = '#/studio'
export const LOGIN_HASH = '#/login'
/** The sign-in page, opened on "Create account". */
export const SIGNUP_HASH = '#/login/new'
export const ADMIN_HASH = '#/admin'
/** The start of an emailed password reset link; the token follows. */
export const RESET_HASH_PREFIX = '#/login/reset/'

/** The token in a reset link's address, or null. */
export function resetTokenFromHash(hash: string): string | null {
  if (!hash.startsWith(RESET_HASH_PREFIX)) return null
  const token = hash.slice(RESET_HASH_PREFIX.length)
  return token.length >= 20 ? token : null
}

const is = (hash: string, route: string) => hash === route || hash.startsWith(`${route}/`)

/** Works out the screen from a hash such as "" or "#/studio". */
export function screenFromHash(hash: string): Screen {
  if (is(hash, STUDIO_HASH)) return 'studio'
  if (is(hash, LOGIN_HASH)) return 'login'
  if (is(hash, ADMIN_HASH)) return 'admin'
  return 'welcome'
}
