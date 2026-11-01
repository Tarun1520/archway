import { useCallback, useEffect, useRef, useState } from 'react'
import type { StreamEvent } from '../lib/api/types'

/** The event names the backend's demo stream sends (backend/app/events/demo_events.py). */
const EVENT_NAMES = ['demo_notice', 'node_started', 'node_finished', 'node_waiting', 'activity', 'stream_finished']

type StreamStatus = 'idle' | 'playing' | 'finished' | 'failed'

/**
 * Plays the backend's DEMO event stream.
 *
 * The browser's built-in `EventSource` keeps one connection open and calls us
 * each time the server sends an event (server-sent events). These events are
 * sample data: the backend marks every one with `demo: true`, and the UI
 * labels them as demo data.
 *
 * In Phase 2 the same idea will listen to a real run's events instead.
 */
export function useDemoEvents() {
  const [events, setEvents] = useState<StreamEvent[]>([])
  const [status, setStatus] = useState<StreamStatus>('idle')
  const source = useRef<EventSource | null>(null)

  const stop = useCallback(() => {
    source.current?.close()
    source.current = null
  }, [])

  const play = useCallback(() => {
    stop()
    setEvents([])
    setStatus('playing')

    const stream = new EventSource('/api/demo/events')
    source.current = stream

    for (const name of EVENT_NAMES) {
      stream.addEventListener(name, (event) => {
        const message = event as MessageEvent<string>
        const data = JSON.parse(message.data) as StreamEvent['data']
        setEvents((current) => [...current, { id: message.lastEventId, name, data }])

        // EventSource reconnects by itself when a stream ends, which would
        // replay everything. Close it ourselves on the last event.
        if (name === 'stream_finished') {
          stop()
          setStatus('finished')
        }
      })
    }

    stream.onerror = () => {
      // Only a problem if we did not already finish and close on purpose.
      if (source.current === stream) {
        stop()
        setStatus('failed')
      }
    }
  }, [stop])

  // Close the connection when the screen that uses this goes away.
  useEffect(() => stop, [stop])

  return { events, status, play }
}
