import { studioCopy } from '../../content/studio'
import type { TeamMessage } from '../../lib/api/types'
import { agentLabel, formatWhen } from '../../lib/research'
import { SparkleIcon } from '../ui/icons'

const KIND_LABEL: Record<TeamMessage['kind'], string> = { task: 'Task', report: 'Report', review: 'Review', note: 'Note' }

/**
 * The research team's conversation: every task the lead gave and every report
 * an agent sent back, in order. These are the agents' own words (written by a
 * model), so they carry the sparkle, and they are shown exactly as saved.
 */
export function TeamConversation({ messages }: { messages: TeamMessage[] }) {
  if (messages.length === 0) return <p className="text-body-sm text-ash italic">{studioCopy.teamEmpty}</p>
  return (
    <ol className="flex flex-col gap-8" aria-label={studioCopy.teamHeading}>
      {messages.map((message) => (
        <li
          key={message.id}
          className={`flex flex-col gap-4 rounded-default p-8 ${message.sender === 'research_lead' ? 'bg-obsidian' : 'border border-mist/15'}`}
        >
          <p className="flex flex-wrap items-center gap-6 text-caption text-ash">
            <SparkleIcon size={12} />
            <span className="text-ivory">{agentLabel(message.sender)}</span>→<span className="text-ivory">{agentLabel(message.recipient)}</span>
            <span className="font-mono">{KIND_LABEL[message.kind]}</span>
            <span>{formatWhen(message.created_at)}</span>
          </p>
          <p className="text-body-sm whitespace-pre-wrap text-ivory">{message.content}</p>
        </li>
      ))}
    </ol>
  )
}
