import { describe, expect, it } from 'vitest'
import { resetTokenFromHash, screenFromHash } from './hashRoute'

describe('screenFromHash', () => {
  it('shows the welcome page when there is no hash', () => {
    expect(screenFromHash('')).toBe('welcome')
  })

  it('shows the studio for #/studio', () => {
    expect(screenFromHash('#/studio')).toBe('studio')
    expect(screenFromHash('#/studio/anything')).toBe('studio')
  })

  it('keeps in-page links on the welcome page', () => {
    expect(screenFromHash('#how-it-works')).toBe('welcome')
    expect(screenFromHash('#start')).toBe('welcome')
  })

  it('does not mistake a longer word for the studio', () => {
    expect(screenFromHash('#/studios')).toBe('welcome')
  })

  it('shows the sign-in page and the admin dashboard', () => {
    expect(screenFromHash('#/login')).toBe('login')
    expect(screenFromHash('#/admin')).toBe('admin')
    expect(screenFromHash('#/administrator')).toBe('welcome')
  })
})

describe('resetTokenFromHash', () => {
  it('reads the token from an emailed reset link, which opens the sign-in page', () => {
    const token = 'abcDEF123_-abcDEF123_-abcDEF123_-abcDEF12'
    expect(resetTokenFromHash(`#/login/reset/${token}`)).toBe(token)
    expect(screenFromHash(`#/login/reset/${token}`)).toBe('login')
  })

  it('ignores other addresses and tokens too short to be real', () => {
    expect(resetTokenFromHash('#/login')).toBeNull()
    expect(resetTokenFromHash('#/login/reset/short')).toBeNull()
  })
})
