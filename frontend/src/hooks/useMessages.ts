import { useCallback, useEffect, useState } from 'react'
import { addMessage, listMessages } from '../lib/api/client'
import type { Message } from '../lib/api/types'

/**
 * Loads the chat messages of one project and adds new ones.
 * When `projectId` changes (another project was selected), it loads again.
 */
export function useMessages(projectId: string | null) {
  const [messages, setMessages] = useState<Message[]>([])
  const [problem, setProblem] = useState<string | null>(null)

  useEffect(() => {
    setMessages([])
    setProblem(null)
    if (projectId === null) return

    let cancelled = false
    listMessages(projectId)
      .then((loaded) => {
        if (!cancelled) setMessages(loaded)
      })
      .catch((error: unknown) => {
        const reason = error instanceof Error ? error.message : 'unknown error'
        if (!cancelled) setProblem(`Messages could not be loaded: ${reason}`)
      })
    return () => {
      cancelled = true
    }
  }, [projectId])

  const send = useCallback(
    async (content: string): Promise<boolean> => {
      if (projectId === null) return false
      try {
        const saved = await addMessage(projectId, content)
        setMessages((current) => [...current, saved])
        setProblem(null)
        return true
      } catch (error) {
        const reason = error instanceof Error ? error.message : 'unknown error'
        setProblem(`The message was not saved: ${reason}`)
        return false
      }
    },
    [projectId],
  )

  return { messages, problem, send }
}
