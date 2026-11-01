/**
 * The microphone, turned into the audio the speech service expects:
 * 16-bit samples, 16 000 per second, one channel, in pieces of 0.1 s.
 *
 * Browsers record at 44 100 or 48 000 samples a second, so the sound is
 * resampled on the way. That work runs in an "AudioWorklet": a small piece of
 * code the browser runs on its own audio thread, so the page never stutters.
 * It also measures how loud each piece is, for the listening meter.
 */

export interface MicCapture {
  stop(): void
}

/** The worklet's code. It is sent to the browser as a tiny file made on the spot. */
const WORKLET = `
class Pcm16Writer extends AudioWorkletProcessor {
  constructor() {
    super()
    this.step = sampleRate / 16000   // how far to move through the input for each output sample
    this.position = 0
    this.out = new Int16Array(1600)  // 0.1 s at 16 000 a second
    this.filled = 0
    this.energy = 0
  }
  process(inputs) {
    const input = inputs[0] && inputs[0][0]
    if (!input) return true
    while (this.position < input.length - 1) {
      const i = Math.floor(this.position)
      const between = this.position - i
      const value = input[i] + (input[i + 1] - input[i]) * between  // straight-line blend of the two nearest samples
      const clipped = Math.max(-1, Math.min(1, value))
      this.out[this.filled++] = clipped < 0 ? clipped * 0x8000 : clipped * 0x7fff
      this.energy += clipped * clipped
      if (this.filled === this.out.length) {
        const level = Math.sqrt(this.energy / this.out.length)
        this.port.postMessage({ pcm: this.out.buffer, level }, [this.out.buffer])
        this.out = new Int16Array(1600)
        this.filled = 0
        this.energy = 0
      }
      this.position += this.step
    }
    this.position -= input.length - 1
    return true
  }
}
registerProcessor('pcm16-writer', Pcm16Writer)
`

/**
 * Starts the microphone. The browser asks the person for permission the first
 * time; if they refuse, this throws and nothing is recorded.
 */
export async function startMic(onAudio: (pcm: ArrayBuffer) => void, onLevel: (level: number) => void): Promise<MicCapture> {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
  })
  const context = new AudioContext()
  await context.resume() // a context made without a fresh click can start suspended: it would record silence
  const moduleUrl = URL.createObjectURL(new Blob([WORKLET], { type: 'application/javascript' }))
  try {
    await context.audioWorklet.addModule(moduleUrl)
  } finally {
    URL.revokeObjectURL(moduleUrl)
  }
  const source = context.createMediaStreamSource(stream)
  const writer = new AudioWorkletNode(context, 'pcm16-writer')
  writer.port.onmessage = (event: MessageEvent<{ pcm: ArrayBuffer; level: number }>) => {
    onAudio(event.data.pcm)
    onLevel(event.data.level)
  }
  source.connect(writer)

  let stopped = false
  return {
    stop() {
      if (stopped) return // stopping twice is harmless
      stopped = true
      writer.port.onmessage = null
      source.disconnect()
      writer.disconnect()
      for (const track of stream.getTracks()) track.stop() // turns the browser's "recording" light off
      void context.close().catch(() => undefined)
    },
  }
}
