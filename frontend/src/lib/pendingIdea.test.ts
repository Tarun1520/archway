import { describe, expect, it } from 'vitest'
import { projectNameFromIdea, takePendingIdea } from './pendingIdea'
import { PENDING_IDEA_KEY } from './startProject'

/** A stand-in for browser storage. */
function createFakeStorage(initial: Record<string, string> = {}) {
  const saved = new Map(Object.entries(initial))
  return {
    saved,
    getItem: (key: string) => saved.get(key) ?? null,
    removeItem: (key: string) => {
      saved.delete(key)
    },
  }
}

describe('takePendingIdea', () => {
  it('returns the idea once and then forgets it', () => {
    const storage = createFakeStorage({ [PENDING_IDEA_KEY]: 'A notes app' })

    expect(takePendingIdea(storage)).toBe('A notes app')
    expect(takePendingIdea(storage)).toBeNull()
    expect(storage.saved.has(PENDING_IDEA_KEY)).toBe(false)
  })

  it('returns null when nothing is waiting', () => {
    expect(takePendingIdea(createFakeStorage())).toBeNull()
  })

  it('returns null when storage is blocked', () => {
    const blocked = {
      getItem: () => {
        throw new Error('blocked')
      },
      removeItem: () => {},
    }
    expect(takePendingIdea(blocked)).toBeNull()
  })
})

describe('projectNameFromIdea', () => {
  it('keeps a short idea as it is, on one line', () => {
    expect(projectNameFromIdea('  A notes\n app  ')).toBe('A notes app')
  })

  it('shortens a long idea at a word boundary', () => {
    const name = projectNameFromIdea('A notes app that stores everything as markdown and searches by meaning', 30)
    expect(name).toBe('A notes app that stores…')
    expect(name.length).toBeLessThanOrEqual(31)
  })
})
