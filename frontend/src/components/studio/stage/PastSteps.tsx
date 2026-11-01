import { studioUi } from '../../../content/studio'
import type { AskedQuestion, Message } from '../../../lib/api/types'

/**
 * Read-only views of steps the project has already passed, for when the user
 * clicks back to one. Nothing here can be changed: the run has moved on.
 */

/** The idea step, looking back: the user's own messages, in order. */
export function PastIdea({ messages }: { messages: Message[] }) {
  const said = messages.filter((message) => message.role === 'user')
  return (
    <section aria-label={studioUi.pastIdea} className="flex max-w-3xl flex-col gap-16">
      <p className="font-code text-label uppercase text-smoke">{studioUi.pastIdea}</p>
      {said.length === 0 ? (
        <p className="text-lead text-smoke">{studioUi.noMessages}</p>
      ) : (
        <ol className="flex flex-col gap-12">
          {said.map((message) => (
            <li key={message.id} className="rounded-card border border-line bg-carbon/70 p-20 text-[17px] leading-[1.6] whitespace-pre-wrap text-chalk">
              {message.content}
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}

/** The questions step, looking back: each question and what the user answered (or that it was skipped). */
export function PastQuestions({ questions }: { questions: AskedQuestion[] }) {
  return (
    <section aria-label={studioUi.pastQuestions} className="flex max-w-3xl flex-col gap-16">
      <p className="font-code text-label uppercase text-smoke">{studioUi.pastQuestions}</p>
      {questions.length === 0 ? (
        <p className="text-lead text-smoke">{studioUi.noQuestions}</p>
      ) : (
        <ol className="flex flex-col border-t border-line">
          {questions.map((item, index) => (
            <li key={item.topic} className="grid grid-cols-[40px_1fr] gap-16 border-b border-line py-20">
              <span className="font-code text-label text-smoke">{String(index + 1).padStart(2, '0')}</span>
              <div className="flex flex-col gap-8">
                <p className="text-[17px] font-semibold text-chalk">{item.question}</p>
                {item.answer ? (
                  <p className="text-[16px] leading-[1.6] text-chalk/85">{item.answer}</p>
                ) : (
                  <p className="text-[15px] text-smoke italic">{studioUi.skipped}</p>
                )}
              </div>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
