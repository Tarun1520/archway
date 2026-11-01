/**
 * Archy's voice: plays a line of text, spoken by the voice service.
 *
 * How a line is played
 *   1. The line is cut into sentences (sentences.ts).
 *   2. Every sentence is requested from /api/voice/speak at the same time, so
 *      they are made in parallel.
 *   3. As each one arrives it is decoded and scheduled to start exactly when the
 *      one before it ends, so the sentences join up without gaps.
 *   The first sound is heard when the FIRST sentence is ready, not the whole line.
 *
 * Lines that repeat (his introduction, "shall I continue?") are kept after the
 * first time, and `warm()` can fetch lines before they are needed, so they
 * start at once.
 *
 * Browsers only let a page play sound after the person has clicked something;
 * `primeSpeaker()` is called inside the click that wakes Archy, which unlocks
 * sound for every line after it.
 */
import { splitSentences } from './sentences'

let context: AudioContext | null = null
let analyser: AnalyserNode | null = null
let volumeNode: GainNode | null = null
let samples: Float32Array<ArrayBuffer> | null = null
let finishLine: (() => void) | null = null
let playing: AudioBufferSourceNode[] = []
let speaking = false

/** Sentences already made (or being made), by voice, speed and words. */
const KEPT_LIMIT = 60
const kept = new Map<string, Promise<AudioBuffer | null>>()

/** Call inside a click: unlocks sound for the lines that follow. */
export function primeSpeaker(): void {
  if (!context) {
    try {
      context = new AudioContext()
      volumeNode = context.createGain()
      analyser = context.createAnalyser()
      analyser.fftSize = 512
      samples = new Float32Array(analyser.fftSize)
      volumeNode.connect(analyser)
      analyser.connect(context.destination)
    } catch {
      context = null // no sound output: lines are shown and timed, but not heard
      return
    }
  }
  void context.resume()
  // A moment of silence, played inside the click, is what unlocks audio in the strictest browsers.
  const blip = context.createBufferSource()
  blip.buffer = context.createBuffer(1, 800, 8000)
  blip.connect(context.destination)
  blip.start()
}

export interface SayOptions {
  /** A voice id; the backend's default when left out. */
  voice?: string
  /** 0.7 to 1.5. */
  speed?: number
  /** 0 to 1. */
  volume?: number
  /** False: nothing is played; the line just takes about as long as it would to read. */
  speak?: boolean
  /** Called once, when the first sound starts (or at once if nothing will be heard). */
  onStart?: () => void
}

/** How long to leave a line on screen when it is not spoken, in milliseconds. */
export function readingTime(text: string): number {
  return Math.min(9000, 1100 + text.length * 55)
}

function keyFor(text: string, options: SayOptions): string {
  return `${options.voice ?? ''}|${options.speed ?? 1}|${text}`
}

/** One sentence as sound: from the cache, or requested now. Null when it could not be made. */
function sentenceSound(text: string, options: SayOptions): Promise<AudioBuffer | null> {
  const key = keyFor(text, options)
  const hit = kept.get(key)
  if (hit) return hit
  const query = new URLSearchParams({ text })
  if (options.voice) query.set('voice', options.voice)
  if (options.speed && options.speed !== 1) query.set('speed', String(options.speed))
  const made = (async () => {
    const response = await fetch(`/api/voice/speak?${query}`)
    if (!response.ok || !context) return null
    return await context.decodeAudioData(await response.arrayBuffer())
  })().catch(() => null)
  kept.set(key, made)
  void made.then((sound) => {
    if (!sound) kept.delete(key) // a failure is not remembered: the next try asks again
  })
  while (kept.size > KEPT_LIMIT) kept.delete(kept.keys().next().value as string)
  return made
}

/** Starts making these lines now, so they are ready when Archy says them. */
export function warm(lines: string[], options: SayOptions = {}): void {
  if (!context || options.speak === false) return
  for (const line of lines) for (const sentence of splitSentences(line)) void sentenceSound(sentence, options)
}

/** Says one line. Resolves when it has been spoken (or was stopped, or failed). */
export function say(text: string, options: SayOptions = {}): Promise<void> {
  hush()
  let started = false
  const start = () => {
    if (started) return
    started = true
    options.onStart?.()
  }
  const ctx = context
  if (options.speak === false || !ctx || !volumeNode) {
    start()
    return new Promise<void>((resolve) => {
      const timer = window.setTimeout(() => finishLine?.(), options.speak === false ? readingTime(text) : 0)
      finishLine = () => {
        window.clearTimeout(timer)
        finishLine = null
        resolve()
      }
    })
  }

  const pieces = splitSentences(text).map((sentence) => sentenceSound(sentence, options)) // all requested together
  volumeNode.gain.value = Math.min(1, Math.max(0, options.volume ?? 1))
  return new Promise<void>((resolve) => {
    let over = false
    const finish = () => {
      if (over) return
      over = true
      speaking = false
      playing = []
      if (finishLine === finish) finishLine = null
      start() // if nothing could be played, the line is still shown
      resolve()
    }
    finishLine = finish
    void (async () => {
      let nextAt = 0
      let last: AudioBufferSourceNode | null = null
      for (const piece of pieces) {
        const sound = await piece
        if (over) return
        if (!sound) continue // a sentence the service refused is skipped
        const source = ctx.createBufferSource()
        source.buffer = sound
        source.connect(volumeNode as GainNode)
        nextAt = Math.max(nextAt, ctx.currentTime + 0.02)
        source.start(nextAt)
        nextAt += sound.duration
        playing.push(source)
        last = source
        if (!speaking) {
          speaking = true
          start()
        }
      }
      if (!last) return finish()
      last.onended = finish
    })()
  })
}

/** Stops the line being spoken, at once. */
export function hush(): void {
  for (const source of playing) {
    source.onended = null
    try {
      source.stop()
    } catch {
      // already finished
    }
  }
  playing = []
  speaking = false
  finishLine?.()
}

/** How loud Archy is right now, 0 (silent) to about 1. Read once per frame for the mouth. */
export function speakingLevel(): number {
  if (!analyser || !samples || !speaking) return 0
  analyser.getFloatTimeDomainData(samples)
  let energy = 0
  for (const value of samples) energy += value * value
  return Math.min(1, Math.sqrt(energy / samples.length) * 4)
}
