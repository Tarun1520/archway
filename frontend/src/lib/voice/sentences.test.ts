import { describe, expect, it } from 'vitest'
import { splitSentences } from './sentences'

describe('splitSentences', () => {
  it('keeps a short line whole', () => {
    expect(splitSentences('Hello there, I am Archy.')).toEqual(['Hello there, I am Archy.'])
  })

  it('cuts at sentence ends, and joins very short sentences to a neighbour', () => {
    const pieces = splitSentences('Hi! I am Archy, the voice agent of this studio. Tell me what you would like to build today.')
    expect(pieces).toEqual(['Hi! I am Archy, the voice agent of this studio.', 'Tell me what you would like to build today.'])
  })

  it('breaks a very long sentence at a comma', () => {
    const long = 'First we look at what you want to build, then we look at who it is for and how they will use it every day, then we talk about the cost and the time it will take, and last we write it all down.'
    const pieces = splitSentences(long)
    expect(pieces.length).toBeGreaterThan(1)
    expect(pieces.join(' ').replace(/\s+/g, ' ')).toBe(long)
    expect(pieces.every((piece) => piece.length <= 150)).toBe(true)
  })

  it('returns nothing for blank text', () => {
    expect(splitSentences('   ')).toEqual([])
  })
})
