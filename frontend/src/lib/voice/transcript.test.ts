import { describe, expect, it } from 'vitest'
import { NOTHING_HEARD, addResult, fullText, onlyFillers } from './transcript'

describe('transcript', () => {
  it('keeps settled phrases and replaces the guess for the phrase being spoken', () => {
    let heard = addResult(NOTHING_HEARD, 'I want', false)
    heard = addResult(heard, 'I want an app', false)
    expect(fullText(heard)).toBe('I want an app')
    heard = addResult(heard, 'I want, um, an app.', true)
    heard = addResult(heard, 'for my', false)
    expect(fullText(heard)).toBe('I want, um, an app. for my')
    heard = addResult(heard, '', true)
    expect(fullText(heard)).toBe('I want, um, an app.')
  })

  it('knows when only fillers were said', () => {
    expect(onlyFillers('Um. Hmm, uh.')).toBe(true)
    expect(onlyFillers('')).toBe(true)
    expect(onlyFillers('Um, a recipe app')).toBe(false)
    expect(onlyFillers('అవును')).toBe(false)
  })
})
