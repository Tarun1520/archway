/**
 * Everything the person can change about ARCHY, in one place.
 *
 * The values live in this browser (localStorage), so they are still there
 * next time. Anything read back is checked and clamped, so a stale or edited
 * value can never put Archy in a state he cannot work in.
 */

export type IntroMode = 'first' | 'always' | 'never'

export interface ArchySettings {
  /** The voice Archy speaks with (an id such as "aura-2-thalia-en"). */
  voice: string
  /** How fast Archy talks: 0.7 (slow) to 1.5 (fast). */
  speed: number
  /** How loud Archy is: 0 to 1. */
  volume: number
  /** Whether Archy speaks aloud at all. Off: his lines only appear as text. */
  speak: boolean
  /** Seconds of quiet that mean "my idea is done". */
  pauseSeconds: number
  /** When Archy introduces himself. */
  intro: IntroMode
  /** Whether Archy plays tricks in the air (skydiving, flips ...) while he waits. */
  tricks: boolean
}

export const DEFAULT_SETTINGS: ArchySettings = {
  voice: 'aura-2-thalia-en',
  speed: 1,
  volume: 1,
  speak: true,
  pauseSeconds: 4,
  intro: 'first',
  tricks: true,
}

export const LIMITS = {
  speed: { min: 0.7, max: 1.5, step: 0.05 },
  volume: { min: 0, max: 1, step: 0.05 },
  pauseSeconds: { min: 2, max: 8, step: 1 },
}

const STORAGE_KEY = 'archway.archySettings'
const VOICE_ID = /^aura-2-[a-z]{3,20}-[a-z]{2}$/
const INTROS: IntroMode[] = ['first', 'always', 'never']

const clamp = (value: unknown, min: number, max: number, fallback: number) =>
  typeof value === 'number' && Number.isFinite(value) ? Math.min(max, Math.max(min, value)) : fallback

const flag = (value: unknown, fallback: boolean) => (typeof value === 'boolean' ? value : fallback)

/** Takes anything (for example, whatever was stored) and returns settings that are safe to use. */
export function cleanSettings(raw: unknown): ArchySettings {
  const given = typeof raw === 'object' && raw !== null ? (raw as Record<string, unknown>) : {}
  const d = DEFAULT_SETTINGS
  return {
    voice: typeof given.voice === 'string' && VOICE_ID.test(given.voice) ? given.voice : d.voice,
    speed: clamp(given.speed, LIMITS.speed.min, LIMITS.speed.max, d.speed),
    volume: clamp(given.volume, LIMITS.volume.min, LIMITS.volume.max, d.volume),
    speak: flag(given.speak, d.speak),
    pauseSeconds: Math.round(clamp(given.pauseSeconds, LIMITS.pauseSeconds.min, LIMITS.pauseSeconds.max, d.pauseSeconds)),
    intro: typeof given.intro === 'string' && INTROS.includes(given.intro as IntroMode) ? (given.intro as IntroMode) : d.intro,
    tricks: flag(given.tricks, d.tricks),
  }
}

export function loadSettings(storage?: Pick<Storage, 'getItem'>): ArchySettings {
  try {
    const raw = (storage ?? window.localStorage).getItem(STORAGE_KEY)
    return cleanSettings(raw ? JSON.parse(raw) : null)
  } catch {
    return DEFAULT_SETTINGS // storage blocked or the text is damaged: start from the defaults
  }
}

export function saveSettings(settings: ArchySettings, storage?: Pick<Storage, 'setItem'>): void {
  try {
    ;(storage ?? window.localStorage).setItem(STORAGE_KEY, JSON.stringify(settings))
  } catch {
    // Not remembered this time; the settings still apply now.
  }
}
