import { describe, expect, it } from 'vitest'
import { MAX_IDEA_LENGTH, PENDING_IDEA_KEY, startProject } from './startProject'

/** A stand-in for browser storage that records what was saved. */
function createFakeStorage() {
  const saved = new Map<string, string>()
  return {
    saved,
    setItem(key: string, value: string) {
      saved.set(key, value)
    },
  }
}

describe('startProject', () => {
  it('saves a trimmed idea and reports success', () => {
    const storage = createFakeStorage()

    const result = startProject('  A recipe manager for my family  ', storage)

    expect(result).toEqual({ ok: true, idea: 'A recipe manager for my family' })
    expect(storage.saved.get(PENDING_IDEA_KEY)).toBe('A recipe manager for my family')
  })

  it('rejects an idea that is empty or only spaces, and saves nothing', () => {
    const storage = createFakeStorage()

    expect(startProject('', storage)).toEqual({ ok: false, reason: 'empty' })
    expect(startProject('   \n ', storage)).toEqual({ ok: false, reason: 'empty' })
    expect(storage.saved.size).toBe(0)
  })

  it('rejects an idea longer than the limit, and saves nothing', () => {
    const storage = createFakeStorage()

    const result = startProject('a'.repeat(MAX_IDEA_LENGTH + 1), storage)

    expect(result).toEqual({ ok: false, reason: 'too_long' })
    expect(storage.saved.size).toBe(0)
  })

  it('accepts an idea exactly at the limit', () => {
    const storage = createFakeStorage()

    expect(startProject('a'.repeat(MAX_IDEA_LENGTH), storage).ok).toBe(true)
  })

  it('reports a storage failure instead of claiming success', () => {
    const brokenStorage = {
      setItem() {
        throw new Error('storage is blocked')
      },
    }

    expect(startProject('A habit tracker', brokenStorage)).toEqual({
      ok: false,
      reason: 'storage_unavailable',
    })
  })
})
