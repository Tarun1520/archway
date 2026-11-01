/**
 * One live listening session: the microphone goes to the backend
 * (/api/voice/listen), the words come back as they are recognised.
 *
 * The backend passes the audio on to the speech service with the key, so the
 * key never reaches this page.
 */
import { getVoicePass } from '../api/client'
import { startMic, type MicCapture } from './micCapture'

export interface ListenHandlers {
  /** Words heard: `final` is false while the phrase may still change. */
  onWords(text: string, final: boolean): void
  /** How loud the microphone is, 0 (silent) and up, about ten times a second. */
  onLevel(level: number): void
  /** Something went wrong; listening has stopped. */
  onError(message: string): void
}

export interface ListenSession {
  /** Ends listening, waiting (briefly) for the last words to arrive. */
  stop(): Promise<void>
  /** Ends listening at once. */
  cancel(): void
}

const READY_TIMEOUT_MS = 8000
const FINISH_TIMEOUT_MS = 2500

/** Why the microphone could not start, in words for the person. */
export class MicrophoneProblem extends Error {}

export async function startListening(language: string, handlers: ListenHandlers, fillers = true): Promise<ListenSession> {
  // On Vercel the WebSocket cannot be forwarded, so it goes straight to the server, which does not see the
  // sign-in cookie there: a one-time pass (asked for through the normal, cookie-carrying /api) stands in for it.
  const { voice_pass: voicePass, socket_url: socketUrl } = await getVoicePass()
  const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws'
  const base = socketUrl || `${scheme}://${window.location.host}`
  const socket = new WebSocket(`${base}/api/voice/listen?language=${encodeURIComponent(language)}&fillers=${fillers}&pass=${encodeURIComponent(voicePass)}`)
  socket.binaryType = 'arraybuffer'

  // Audio recorded before the connection is ready is kept, so the first word is not lost.
  const waiting: ArrayBuffer[] = []
  let ready = false
  let ended = false
  let stopping = false // we asked for the end ourselves: the line closing afterwards is not a problem
  let finished: (() => void) | null = null

  const send = (pcm: ArrayBuffer) => {
    if (ended) return
    if (ready && socket.readyState === WebSocket.OPEN) socket.send(pcm)
    else waiting.push(pcm)
  }

  // LEARNING NOTE: attach listeners BEFORE anything slow happens.
  //   The backend says "ready" about a second after the socket opens. Starting the microphone can take
  //   longer than that (a permission question, a Bluetooth headset), and a message that arrives while
  //   nobody is listening is simply lost. So these handlers are set at once, and what they hear is
  //   remembered in `readySignal`, which is awaited later.
  let mic: MicCapture | null = null
  const end = () => {
    if (ended) return
    ended = true
    mic?.stop()
    finished?.()
  }
  let markReady: () => void = () => undefined
  let markFailed: (error: Error) => void = () => undefined
  const readySignal = new Promise<void>((resolve, reject) => {
    markReady = resolve
    markFailed = reject
  })
  readySignal.catch(() => undefined) // a failure is reported where it is awaited; this only avoids a stray warning

  socket.onmessage = (event) => {
    if (typeof event.data !== 'string') return
    const message = JSON.parse(event.data) as { type: string; text?: string; final?: boolean; message?: string }
    if (message.type === 'ready') {
      ready = true
      for (const pcm of waiting.splice(0)) socket.send(pcm)
      markReady()
    } else if (message.type === 'transcript') {
      handlers.onWords(message.text ?? '', Boolean(message.final))
    } else if (message.type === 'error') {
      markFailed(new Error(message.message ?? 'The voice service failed.'))
      if (ready && !stopping) handlers.onError(message.message ?? 'The voice service failed.')
      end()
    } else if (message.type === 'closed') {
      end()
    }
  }
  socket.onerror = () => markFailed(new Error('Could not connect to the voice service.'))
  socket.onclose = () => {
    if (!ended && !stopping && ready) handlers.onError('The connection to the voice service was lost.')
    markFailed(new Error('The voice service closed the connection before it was ready.'))
    end()
  }

  try {
    mic = await startMic(send, handlers.onLevel)
  } catch (error) {
    ended = true
    socket.close()
    const name = error instanceof Error ? error.name : ''
    throw new MicrophoneProblem(
      name === 'NotAllowedError' || name === 'SecurityError'
        ? 'blocked'
        : name === 'NotFoundError'
          ? 'missing'
          : 'failed',
    )
  }

  // The wait for "ready" starts now, once the microphone is running (a permission question is not counted).
  const timer = window.setTimeout(() => markFailed(new Error('The voice service did not answer in time.')), READY_TIMEOUT_MS)
  try {
    await readySignal
  } catch (error) {
    end()
    socket.close()
    throw error
  } finally {
    window.clearTimeout(timer)
  }

  return {
    async stop() {
      if (ended) return
      stopping = true
      mic?.stop() // no more sound, but keep the connection open for the last words
      if (socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type: 'stop' }))
      await new Promise<void>((resolve) => {
        finished = resolve
        window.setTimeout(resolve, FINISH_TIMEOUT_MS)
      })
      ended = true
      socket.close()
    },
    cancel() {
      end()
      socket.close()
    },
  }
}
