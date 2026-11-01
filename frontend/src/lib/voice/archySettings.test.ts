import { describe, expect, it } from 'vitest'
import { DEFAULT_SETTINGS, cleanSettings, loadSettings, saveSettings } from './archySettings'

describe('archy settings', () => {
  it('uses the defaults for nothing, for rubbish, and for a damaged store', () => {
    expect(cleanSettings(null)).toEqual(DEFAULT_SETTINGS)
    expect(cleanSettings('hello')).toEqual(DEFAULT_SETTINGS)
    expect(loadSettings({ getItem: () => '{not json' })).toEqual(DEFAULT_SETTINGS)
    expect(loadSettings({ getItem: () => { throw new Error('blocked') } })).toEqual(DEFAULT_SETTINGS)
  })

  it('keeps good values and clamps numbers into their range', () => {
    const kept = cleanSettings({ voice: 'aura-2-draco-en', speed: 1.2, volume: 0.4, pauseSeconds: 6, tricks: false, intro: 'never', speak: false })
    expect(kept).toMatchObject({ voice: 'aura-2-draco-en', speed: 1.2, volume: 0.4, pauseSeconds: 6, tricks: false, intro: 'never', speak: false })
    expect(cleanSettings({ speed: 9, volume: -3, pauseSeconds: 100 })).toMatchObject({ speed: 1.5, volume: 0, pauseSeconds: 8 })
    expect(cleanSettings({ pauseSeconds: 3.6 }).pauseSeconds).toBe(4)
  })

  it('refuses a language, voice, intro or flag it does not know', () => {
    const odd = cleanSettings({ language: 'fr', fillers: false, askBeforeBrief: false, voice: '../../x', intro: 'sometimes', speak: 'yes', speed: 'fast' })
    expect(odd).toEqual(DEFAULT_SETTINGS)
  })

  it('saves and loads the same settings', () => {
    let stored = ''
    const settings = { ...DEFAULT_SETTINGS, voice: 'aura-2-hyperion-en', speed: 0.8 }
    saveSettings(settings, { setItem: (_key, value) => { stored = value } })
    expect(loadSettings({ getItem: () => stored })).toEqual(settings)
  })
})
