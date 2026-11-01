import { describe, expect, it } from 'vitest'
import { isModelThinking, onModelThinking, startWaiting } from './modelActivity'

describe('modelActivity', () => {
  it('is thinking while anything waits, and stops only when everything is done', () => {
    const seen: boolean[] = []
    const stop = onModelThinking((thinking) => seen.push(thinking))
    const first = startWaiting()
    const second = startWaiting()
    expect(isModelThinking()).toBe(true)
    first()
    expect(isModelThinking()).toBe(true)
    second()
    second() // finishing twice changes nothing
    expect(isModelThinking()).toBe(false)
    expect(seen.at(-1)).toBe(false)
    stop()
  })
})
