import { useEffect, useRef, useState } from 'react'
import type { FormEvent, KeyboardEvent } from 'react'
import { studioCopy } from '../../content/studio'
import type { Message } from '../../lib/api/types'
import { StudioButton } from './StudioButton'
import { AlertIcon } from '../ui/icons'

/** What ARCHY, the voice agent, is doing with this chat box. */
export interface VoiceInput {
  /** True while he is listening for the idea: what is heard is typed into the box. */
  listening: boolean
  /** The words heard so far. */
  text: string
  /** Counts up each time a spoken idea was saved as a message: the box then empties itself. */
  sent: number
}

interface ChatPanelProps {
  messages: Message[]
  problem: string | null
  /** Saves a message. Resolves to true when it was saved. */
  onSend: (content: string) => Promise<boolean>
  voice?: VoiceInput
  /** Tells the page what is in the box (so a spoken idea is saved together with anything typed before it). */
  onDraft?: (draft: string) => void
}

/** What was already in the box, then what was said. */
const compose = (base: string, spoken: string) => [base.trim(), spoken.trim()].filter(Boolean).join(' ')

const roleLabels: Record<Message['role'], string> = {
  user: 'You',
  assistant: 'Archway',
  system: 'System',
}

/**
 * The chat for the selected project.
 *
 * A message is saved to the backend's database. "Create brief" (in the studio
 * page) then hands every saved message to the workflow, which drafts a brief.
 * Archway does not reply in the chat itself.
 *
 * With ARCHY listening, whatever is said is typed into the box as it is
 * heard, after anything already there (typing is paused while he listens).
 * It stays editable afterwards, and "Send" (or saying yes to ARCHY) saves it.
 */
export function ChatPanel({ messages, problem, onSend, voice, onDraft }: ChatPanelProps) {
  const [draft, setDraft] = useState('')
  const [sending, setSending] = useState(false)
  const box = useRef<HTMLTextAreaElement>(null)

  // Spoken words go into the box. `base` is what was in the box when listening began.
  const base = useRef('')
  const wasListening = useRef(false)
  const listening = voice?.listening ?? false
  const spoken = voice?.text ?? ''
  const lastSpoken = useRef(spoken)
  useEffect(() => {
    if (listening && !wasListening.current && spoken === '') base.current = draft // a fresh start; a resumed one keeps its base
    wasListening.current = listening
    // While he listens the words are typed in as they come; after he stops, a change to them (the cleaned-up
    // version of what was said) is shown too. A person's own edits afterwards are left alone.
    if (listening || spoken !== lastSpoken.current) setDraft(compose(base.current, spoken))
    lastSpoken.current = spoken
  }, [listening, spoken]) // eslint-disable-line react-hooks/exhaustive-deps

  // A spoken idea was saved as a message: the box starts empty again.
  const sentBefore = useRef(voice?.sent ?? 0)
  useEffect(() => {
    const sent = voice?.sent ?? 0
    if (sent !== sentBefore.current) {
      sentBefore.current = sent
      base.current = ''
      setDraft('')
    }
  }, [voice?.sent])

  useEffect(() => {
    onDraft?.(draft)
    return () => onDraft?.('') // the box is going away: nothing is waiting in it any more
  }, [draft]) // eslint-disable-line react-hooks/exhaustive-deps

  // The box grows with what is in it (up to about six lines), then scrolls.
  useEffect(() => {
    const element = box.current
    if (!element) return
    element.style.height = 'auto'
    element.style.height = `${Math.min(element.scrollHeight, 168)}px`
  }, [draft])

  const send = async () => {
    const content = draft.trim()
    if (content === '' || sending || listening) return

    setSending(true)
    const saved = await onSend(content)
    setSending(false)
    // Keep the text if saving failed, so nothing typed is lost.
    if (saved) {
      base.current = ''
      setDraft('')
    }
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    void send()
  }

  // Enter sends; Shift+Enter starts a new line.
  const handleKey = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      void send()
    }
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {/* aria-live makes screen readers announce new messages as they arrive. */}
      <ol aria-live="polite" className="flex min-h-0 flex-1 flex-col gap-12 overflow-y-auto p-20">
        {messages.length === 0 && <li className="text-body-sm text-ash">{studioCopy.chatEmpty}</li>}
        {messages.map((message) => (
          <li key={message.id} className="max-w-640 rounded-card bg-obsidian px-16 py-12">
            <p className="text-caption font-strong text-ash">{roleLabels[message.role]}</p>
            <p className="mt-4 text-body whitespace-pre-wrap text-ivory">{message.content}</p>
          </li>
        ))}
      </ol>

      <form onSubmit={handleSubmit} className="border-t border-mist/10 p-16">
        <div className="flex flex-col gap-12 sm:flex-row sm:items-end">
          <label htmlFor="chat-input" className="sr-only">
            {studioCopy.chatPlaceholder}
          </label>
          <textarea
            ref={box}
            id="chat-input"
            rows={1}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={handleKey}
            readOnly={listening}
            placeholder={listening ? studioCopy.chatListening : studioCopy.chatPlaceholder}
            maxLength={8000}
            autoComplete="off"
            aria-busy={listening}
            className={`min-h-44 min-w-0 flex-1 resize-none rounded-control border bg-transparent px-20 py-[10px] text-body leading-[1.5] text-ivory transition-colors ${
              listening ? 'border-[#7fe8ff]/60' : 'border-mist/25'
            }`}
          />
          <StudioButton type="submit" variant="outline" disabled={sending} className="shrink-0">
            {studioCopy.chatSend}
          </StudioButton>
        </div>

        {problem ? (
          <p role="alert" className="mt-8 inline-flex items-start gap-8 text-body-sm text-ivory">
            <span className="mt-2 shrink-0">
              <AlertIcon size={16} />
            </span>
            {problem}
          </p>
        ) : (
          <p className="mt-8 text-caption text-ash">{studioCopy.chatNotice}</p>
        )}
      </form>
    </div>
  )
}
